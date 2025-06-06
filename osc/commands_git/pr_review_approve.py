import osc.commandline_git


class PullRequestReviewApproveCommand(osc.commandline_git.GitObsCommand):
    """
    Approve pull request reviews
    """

    name = "approve"
    parent = "PullRequestReviewCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "--message",
            help="Justification of the review state change",
        )
        self.add_argument(
            "--commit",
            help="Pin the review to the specified commit",
        )

    def run(self, args):
        from osc import gitea_api

        if len(args.id) > 1 and args.commit:
            self.parser.error("The --commit option can be used only with one pull request")

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_index, pr_id in enumerate(pull_request_ids):
            self.print_gitea_settings()

            print(f"Approving {pr_id}...")

            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            gitea_api.PullRequest.approve_review(self.gitea_conn, owner, repo, number, msg=args.message, commit=args.commit)
