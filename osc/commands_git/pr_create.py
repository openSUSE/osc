import re
import sys

import osc.commandline_git


NEW_PULL_REQUEST_TEMPLATE = """
# title
{title}

# description
{description}

#
# Please enter pull request title and description in the following format:
# <title>
# <blank line>
# <description>
#
# Lines starting with '#' will be ignored, and an empty message aborts the operation.
#
# Creating {source_owner}/{source_repo}#{source_branch} -> {target_owner}/{target_repo}#{target_branch}
#
{git_status}
#
# Commits:
{git_commits}
""".lstrip()


class PullRequestCreateCommand(osc.commandline_git.GitObsCommand):
    """
    Create a pull request
    """

    name = "create"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "--title",
            metavar="TEXT",
            help="Pull request title",
        )
        self.add_argument(
            "--description",
            metavar="TEXT",
            help="Pull request description (body)",
        )
        self.add_argument(
            "--source-owner",
            metavar="OWNER",
            help="Owner of the source repo (default: derived from remote URL in local git repo)",
        )
        self.add_argument(
            "--source-repo",
            metavar="REPO",
            help="Name of the source repo (default: derived from remote URL in local git repo)",
        )
        self.add_argument(
            "--source-branch",
            metavar="BRANCH",
            help="Source branch (default: the current branch in local git repo)",
        )
        self.add_argument(
            "--target-owner",
            metavar="OWNER",
            help="Target owner (default: parent of the source repo)",
        )
        self.add_argument(
            "--target-branch",
            metavar="BRANCH",
            help="Target branch (default: derived from the current branch in local git repo)",
        )
        self.add_argument(
            "--project",
            metavar="PROJECT_FOLDER",
            help="Specify a folder with multiple packages (optional)",
        )
        self.add_argument(
            "--force",
            action="store_true",
            help="Force the operation despite branch differences across packages when --project is used",
        )

    def _create_pull_request(self, args):
        from osc import gitea_api

        # the source args are optional, but if one of them is used, the others must be used too
        source_args = (args.source_owner, args.source_repo, args.source_branch)
        if sum((int(i is not None) for i in source_args)) not in (0, len(source_args)):
            self.parser.error("All of the following options must be used together: --source-owner, --source-repo, --source-branch")

        self.print_gitea_settings()

        use_local_git = args.source_owner is None

        if use_local_git:
            # local git repo
            git = gitea_api.Git(".")
            local_owner, local_repo = git.get_owner_repo()
            local_branch = git.current_branch
            local_commit = git.get_branch_head(local_branch)

        # remote git repo - source
        if use_local_git:
            source_owner = local_owner
            source_repo = local_repo
            source_branch = local_branch
        else:
            source_owner = args.source_owner
            source_repo = args.source_repo
            source_branch = args.source_branch
        try:
            source_repo_obj = gitea_api.Repo.get(self.gitea_conn, source_owner, source_repo)
            source_branch_obj = gitea_api.Branch.get(self.gitea_conn, source_owner, source_repo, source_branch)
        except gitea_api.GiteaException:
            raise gitea_api.GitObsRuntimeError(f"Source branch '{source_branch}' does not exist in '{source_owner}/{source_repo}'")
        
        if args.target_owner:
            target_owner = args.target_owner

            target_repo = None
            parents = gitea_api.Repo.get_parent_repos(self.gitea_conn, source_owner, source_repo)
            for parent in parents:
                if parent.owner.lower() == args.target_owner.lower():
                    target_repo = parent.repo
                    break
            if not target_repo:
                raise gitea_api.GitObsRuntimeError(f"Unable to create a pull request because owner '{target_owner}' has no matching parent repo for '{source_owner}/{source_repo}'")
        elif source_repo_obj.parent_obj is None:
            raise gitea_api.GitObsRuntimeError(f"Unable to create a pull request because repo '{source_owner}/{source_repo}' is not a fork")
        else:
            # remote git repo - target
            target_owner = source_repo_obj.parent_obj.owner
            target_repo = source_repo_obj.parent_obj.repo

        if args.target_branch:
            target_branch = args.target_branch
        elif source_branch.startswith("for/"):
            # source branch name format: for/<target-branch>/<what-the-branch-name-would-normally-be>
            target_branch = source_branch.split("/")[1]
        else:
            target_branch = source_branch

        try:
            target_branch_obj = gitea_api.Branch.get(self.gitea_conn, target_owner, target_repo, target_branch)
        except gitea_api.GiteaException:
            raise gitea_api.GitObsRuntimeError(f"Target branch '{target_branch}' does not exist in '{target_owner}/{target_repo}'")

        print("Creating a pull request ...", file=sys.stderr)
        if use_local_git:
            print(f" * Local git: branch: {local_branch}, commit: {local_commit}", file=sys.stderr)
        print(f" * Source: {source_owner}/{source_repo}, branch: {source_branch_obj.name}, commit: {source_branch_obj.commit}", file=sys.stderr)
        print(f" * Target: {target_owner}/{target_repo}, branch: {target_branch_obj.name}, commit: {target_branch_obj.commit}", file=sys.stderr)

        if use_local_git and local_commit != source_branch_obj.commit:
            from osc.output import tty
            print(f"{tty.colorize('ERROR', 'red,bold')}: Local commit doesn't correspond with the latest commit in the remote source branch")
            sys.exit(1)

        if source_branch_obj.commit == target_branch_obj.commit:
            from osc.output import tty
            print(f"{tty.colorize('ERROR', 'red,bold')}: Source and target are identical, make and push changes to the remote source repo first")
            sys.exit(1)

        title = args.title or ""
        description = args.description or ""

        if not title or not description:
            # TODO: add list of commits and list of changed files to the template; requires local git repo
            if use_local_git:
                git_status = git.status(untracked_files=True)
                git_status = "\n".join([f"# {i}" for i in git_status.splitlines()])
            else:
                git_status = "#"

            if use_local_git:
                git_commits = git._run_git(["log", "--format=- %s", f"{target_branch_obj.commit}..{source_branch_obj.commit}"])
                git_commits = "\n".join([f"# {i}" for i in git_commits.splitlines()])
            else:
                git_commits = "#"

            message = gitea_api.edit_message(template=NEW_PULL_REQUEST_TEMPLATE.format(**locals()))

            # remove comments
            message = "\n".join([i for i in message.splitlines() if not i.startswith("#")])

            # strip leading and trailing spaces
            message = message.strip()

            if not message:
                raise gitea_api.GitObsRuntimeError("Aborting operation due to empty title and description.")

            parts = re.split(r"\n\n", message, 1)
            if len(parts) == 1:
                # empty description
                title = parts[0]
                description = ""
            else:
                title = parts[0]
                description = parts[1]

            title = title.strip()
            description = description.strip()

        pr_obj = gitea_api.PullRequest.create(
            self.gitea_conn,
            target_owner=target_owner,
            target_repo=target_repo,
            target_branch=target_branch,
            source_owner=source_owner,
            # source_repo is not required because the information lives in Gitea database
            source_branch=source_branch,
            title=title,
            description=description,
        )

        print("", file=sys.stderr)
        print("Pull request created:", file=sys.stderr)
        print(pr_obj.to_human_readable_string())

    def run(self, args):
        import os
        import subprocess

        if not args.project:
            self._create_pull_request(args)
            return

        print(f"Project folder: {args.project}", file=sys.stderr)

        branches = {}
        for package in os.listdir(args.project):
            package_path = os.path.join(args.project, package)
            if not os.path.isdir(package_path):
                continue

            try:
                branch = subprocess.check_output(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=package_path,
                    stderr=subprocess.PIPE,
                    text=True
                ).strip()
                branches[package] = branch
            except subprocess.CalledProcessError as e:
                print(
                    f"Error checking branch for {package}: {e.stderr}",
                    file=sys.stderr
                )
                return 1

        unique_branches = set(branches.values())
        if len(unique_branches) > 1 and not args.force:
            print(
                "Warning: Packages are on different branches. Use --force to proceed.",
                file=sys.stderr
            )
            for package, branch in branches.items():
                print(f"  - {package}: {branch}", file=sys.stderr)
            return 1

        print(
            "Proceeding with creating pull requests for each package.",
            file=sys.stderr
        )
        
        original_cwd = os.getcwd()
        for package in os.listdir(args.project):
            package_path = os.path.join(args.project, package)
            if not os.path.isdir(package_path):
                continue

            print(f"Processing package: {package}", file=sys.stderr)
            os.chdir(package_path)
            
            self._create_pull_request(args)
            
            os.chdir(original_cwd)

        print("Successfully created all pull requests.", file=sys.stderr)
