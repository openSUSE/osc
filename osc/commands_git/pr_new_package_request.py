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
            help="Package(s) to add (format: <owner>/<repo>:<branch>). If omitted, the current checkout is used. Specify the most significant packages first.",
        )

        self.add_argument(
            "-m",
            "--message",
            help="Additional information (e.g., links to bug trackers) that justify adding the package(s).",
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

        pkg_ids = []
        pkg_names = []
        for pkg_owner, pkg_repo_name, pkg_branch in packages:
            pkg_id = f"{pkg_owner}/{pkg_repo_name}:{pkg_branch}"
            print(f"Verifying {pkg_id} ...", file=sys.stderr)
            gitea_api.Branch.get(self.gitea_conn, pkg_owner, pkg_repo_name, pkg_branch)
            pkg_ids.append(pkg_id)
            pkg_names.append(pkg_repo_name)

        print(f"Creating request for {len(pkg_ids)} package(s) in {target_owner}/{target_repo} ...", file=sys.stderr)

        # We're not sorting the pkg_names, because the user should specify the most significant packages first
        # and we want them in the title.
        max_packages = 5
        updated_packages_str = ", ".join(pkg_names[:max_packages])
        if len(pkg_names) > max_packages:
            updated_packages_str += f" + {len(pkg_names) - max_packages} more"

        title = f"[ADD] Requesting new packages in '{target_branch}': {updated_packages_str}"

        # create body
        body_lines = ["### Package Sources", ""]
        body_lines.extend(pkg_ids)
        body_lines.append("")
        body_lines.append("### Additional Information")
        body_lines.append("")
        if args.message:
            body_lines.append(args.message)
        body = "\n".join(body_lines)

        try:
            issue_obj = gitea_api.Issue.create(
                self.gitea_conn,
                target_owner,
                target_repo,
                title=title,
                body=body,
                ref=target_branch,
            )

            print(f" * Created issue {target_owner}/{target_repo}#{issue_obj.number}: {issue_obj.html_url}", file=sys.stderr)
            issue_obj.add_labels(self.gitea_conn, target_owner, target_repo, labels=[label_id])
            print(f" * Added label '{label}'", file=sys.stderr)

        except gitea_api.GiteaException as e:
            print(f" * {tty.colorize('ERROR', 'red,bold')}: Failed to create issue: {e}", file=sys.stderr)
            sys.exit(1)

        print("", file=sys.stderr)
