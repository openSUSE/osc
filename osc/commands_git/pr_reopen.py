import osc.commandline_git


class PullRequestReopenCommand(osc.commandline_git.GitObsCommand):
    """
    Reopen pull requests
    """

    name = "reopen"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "-m",
            "--message",
            help="Text of the comment",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_index, pr_id in enumerate(pull_request_ids):
            print(f"Reopening {pr_id} ...")
            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)

            gitea_api.PullRequest.reopen(
                self.gitea_conn,
                owner,
                repo,
                number,
            )

            if args.message:
                gitea_api.PullRequest.add_comment(
                    self.gitea_conn,
                    owner,
                    repo,
                    number,
                    msg=args.message,
                )
