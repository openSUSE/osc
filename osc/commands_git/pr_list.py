import sys

import osc.commandline_git


class PullRequestListCommand(osc.commandline_git.GitObsCommand):
    """
    List pull requests in a repository
    """

    name = "list"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument_owner()
        self.add_argument_repo()
        self.add_argument(
            "--state",
            choices=["open", "closed", "all"],
            default="open",
            help="State of the pull requests (default: open)",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        data = gitea_api.PullRequest.list(self.gitea_conn, args.owner, args.repo, state=args.state).json()

        text = gitea_api.PullRequest.list_to_human_readable_string(data, sort=True)
        if text:
            print(text)
            print("", file=sys.stderr)

        print(f"Total entries: {len(data)}", file=sys.stderr)
