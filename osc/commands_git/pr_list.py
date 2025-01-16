import sys

import osc.commandline_git


class PullRequestListCommand(osc.commandline_git.GitObsCommand):
    """
    List pull requests in a repository
    """

    name = "list"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument_owner_repo(nargs="+")
        self.add_argument(
            "--state",
            choices=["open", "closed", "all"],
            default="open",
            help="State of the pull requests (default: open)",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        total_entries = 0
        for owner, repo in args.owner_repo:
            data = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=args.state).json()
            total_entries += len(data)

            text = gitea_api.PullRequest.list_to_human_readable_string(data, sort=True)
            if text:
                print(text)
                print("", file=sys.stderr)

        print(f"Total entries: {total_entries}", file=sys.stderr)
