import osc.commandline_git


class PullRequestReviewCancelRequestCommand(osc.commandline_git.GitObsCommand):
    """
    Cancel a request for review of pull request
    """

    name = "cancel-request"
    parent = "PullRequestReviewCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "user",
            nargs="*",
            help="User with pending review request",
        )
        self.add_argument(
            "-n",
            "--dry-run",
            action="store_true",
            help="Don't do any action, only report what should be done",
        )
        self.add_argument(
            "-a",
            "--all",
            action="store_true",
            help="Cancel all pending review requests",
        )
        self.add_argument(
            "-x",
            "--exclude",
            action="append",
            help="Users to ignore when cancelling review requests.",
        )

    def run(self, args):
        from osc import gitea_api

        if len(args.user) < 1 and not args.all:
            self.parser.error("Must specify a user or --all for all users")

        self.print_gitea_settings()

        owner, repo, number = gitea_api.PullRequest.split_id(args.id)
        if args.all:
            gitea_api.PullRequest.cancel_review_requests_all(
                self.gitea_conn, owner, repo, number, args.exclude, args.dry_run
            )
        else:
            gitea_api.PullRequest.cancel_review_requests(
                self.gitea_conn,
                owner,
                repo,
                number,
                args.user,
                args.exclude,
                args.dry_run,
            )
