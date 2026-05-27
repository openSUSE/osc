import sys

import osc.commandline_git


class PullRequestNewPackageRequestCommand(osc.commandline_git.GitObsCommand):
    """
    Request a new package

    Create a new package request issue in the target repository.
    """

    name = "new-package-request"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument_owner_repo_branch(
            dest="packages",
            nargs="*",
            help="Package(s) to add (format: <owner>/<repo>:<branch>). If omitted, the current checkout is used.",
        )

        self.add_argument_owner_repo_branch(
            "-t",
            "--target",
            dest="target",
            required=True,
            help="Target repository and branch (format: <owner>/<repo>:<branch>)",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        self.print_gitea_settings()

        target_owner, target_repo, target_branch = args.target

        packages = args.packages
        if not packages:
            git = gitea_api.Git(".")
            owner, repo_name = git.get_owner_repo()
            branch = git.current_branch
            packages = [(owner, repo_name, branch)]

        labels = gitea_api.Repo.get_label_ids(self.gitea_conn, target_owner, target_repo)
        label = "new/New Repository"
        label_id = labels.get(label)
        if not label_id:
            raise gitea_api.GitObsRuntimeError(f"Label '{label}' doesn't exist in '{target_owner}/{target_repo}'")

        for pkg_owner, pkg_repo_name, pkg_branch in packages:
            pkg_id = f"{pkg_owner}/{pkg_repo_name}:{pkg_branch}"
            print(f"Verifying {pkg_id} ...", file=sys.stderr)
            try:
                gitea_api.Branch.get(self.gitea_conn, pkg_owner, pkg_repo_name, pkg_branch)
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    print(
                        f" * {tty.colorize('ERROR', 'red,bold')}: Branch {pkg_branch} not found in {pkg_owner}/{pkg_repo_name}",
                        file=sys.stderr,
                    )
                    sys.exit(1)
                # handle other errors
                print(f" * {tty.colorize('ERROR', 'red,bold')}: {e}", file=sys.stderr)
                sys.exit(1)

            print(f"Creating request for {pkg_id} in {target_owner}/{target_repo} ...", file=sys.stderr)
            title = f"[ADD] requesting a new package '{pkg_repo_name}' in '{target_branch}'"
            body = pkg_id

            try:
                issue_obj = gitea_api.Issue.create(
                    self.gitea_conn,
                    target_owner,
                    target_repo,
                    title=title,
                    body=body,
                    ref=target_branch,
                )

                print(f" * Created issue #{issue_obj.number}: {issue_obj.html_url}", file=sys.stderr)
                issue_obj.add_labels(self.gitea_conn, target_owner, target_repo, labels=[label_id])
                print(f" * Added label '{label}'", file=sys.stderr)

            except gitea_api.GiteaException as e:
                print(f" * {tty.colorize('ERROR', 'red,bold')}: Failed to create issue: {e}", file=sys.stderr)
                sys.exit(1)

        print("", file=sys.stderr)
