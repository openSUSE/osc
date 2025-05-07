import os
import re
import subprocess
import sys
from typing import Optional
from typing import List

import osc.commandline_git


def get_editor() -> List[str]:
    import shutil
    import shlex

    editor = os.getenv("EDITOR", None)
    if editor:
        candidates = [editor]
    else:
        candidates = ["vim", "vi"]

    editor_path = None
    args = None
    for i in candidates:
        i, *args = shlex.split(i)
        if i.startswith("/"):
            editor_path = i
        else:
            editor_path = shutil.which(i)

        if editor_path:
            break

    if not editor_path:
        raise RuntimeError(f"Unable to start editor '{candidates[0]}'")

    res = [editor_path]
    if args:
        res += args

    return res


def get_editor_command(file_path: str) -> List[str]:
    res = get_editor()
    res.append(file_path)
    return res


def run_editor(file_path: str):
    subprocess.run(get_editor_command(file_path))


def edit_message(template: Optional[str] = None) -> str:
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", prefix="git_obs_message_") as f:
        if template:
            f.write(template)
            f.flush()

        run_editor(f.name)

        f.seek(0)
        return f.read()


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
            "--target-branch",
            metavar="BRANCH",
            help="Target branch (default: derived from the current branch in local git repo)",
        )

    def run(self, args):
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
            local_rev = git.get_branch_head(local_branch)

        # remote git repo - source
        if use_local_git:
            source_owner = local_owner
            source_repo = local_repo
            source_branch = local_branch
        else:
            source_owner = args.source_owner
            source_repo = args.source_repo
            source_branch = args.source_branch
        source_repo_data = gitea_api.Repo.get(self.gitea_conn, source_owner, source_repo).json()
        source_branch_data = gitea_api.Branch.get(self.gitea_conn, source_owner, source_repo, source_branch).json()
        source_rev = source_branch_data["commit"]["id"]

        # remote git repo - target
        target_owner, target_repo = source_repo_data["parent"]["full_name"].split("/")

        if args.target_branch:
            target_branch = args.target_branch
        elif source_branch.startswith("for/"):
            # source branch name format: for/<target-branch>/<what-the-branch-name-would-normally-be>
            target_branch = source_branch.split("/")[1]
        else:
            target_branch = source_branch

        target_branch_data = gitea_api.Branch.get(self.gitea_conn, target_owner, target_repo, target_branch).json()
        target_rev = target_branch_data["commit"]["id"]

        print("Creating a pull request ...", file=sys.stderr)
        if use_local_git:
            print(f" * Local git: branch: {local_branch}, rev: {local_rev}", file=sys.stderr)
        print(f" * Source: {source_owner}/{source_repo}, branch: {source_branch}, rev: {source_rev}", file=sys.stderr)
        print(f" * Target: {target_owner}/{target_repo}, branch: {target_branch}, rev: {target_rev}", file=sys.stderr)

        if use_local_git and local_rev != source_rev:
            from osc.output import tty
            print(f"{tty.colorize('ERROR', 'red,bold')}: Local commit doesn't correspond with the latest commit in the remote source branch")
            sys.exit(1)

        if source_rev == target_rev:
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

            message = edit_message(template=NEW_PULL_REQUEST_TEMPLATE.format(**locals()))

            # remove comments
            message = "\n".join([i for i in message.splitlines() if not i.startswith("#")])

            # strip leading and trailing spaces
            message = message.strip()

            if not message:
                raise RuntimeError("Aborting operation due to empty title and description.")

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

        pull = gitea_api.PullRequest.create(
            self.gitea_conn,
            target_owner=target_owner,
            target_repo=target_repo,
            target_branch=target_branch,
            source_owner=source_owner,
            # source_repo is not required because the information lives in Gitea database
            source_branch=source_branch,
            title=title,
            description=description,
        ).json()

        print("", file=sys.stderr)
        print("Pull request created:", file=sys.stderr)
        print(gitea_api.PullRequest.to_human_readable_string(pull))
