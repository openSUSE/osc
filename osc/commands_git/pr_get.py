import sys

import osc.commandline_git


class PullRequestGetCommand(osc.commandline_git.GitObsCommand):
    """
    Get details about the specified pull requests
    """

    name = "get"
    aliases = ["show"]  # for compatibility with osc
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "-p",
            "--patch",
            action="store_true",
            help="Show patches associated with the pull requests",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()

        num_entries = 0
        failed_entries = []
        for pr_id in args.id:
            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            try:
                pr = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number).json()
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(pr_id)
                    continue
                raise
            print(gitea_api.PullRequest.to_human_readable_string(pr))

            if args.patch:
                print("")
                print(tty.colorize("Patch:", "bold"))
                patch = gitea_api.PullRequest.get_patch(self.gitea_conn, owner, repo, number).data
                patch = highlight_diff(patch)
                print(patch.decode("utf-8"))

        print(f"Total entries: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(
                f"{tty.colorize('ERROR', 'red,bold')}: Couldn't retrieve the following pull requests: {', '.join(failed_entries)}",
                file=sys.stderr,
            )
            sys.exit(1)
