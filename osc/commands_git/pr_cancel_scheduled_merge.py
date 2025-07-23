import osc.commandline_git


class PullRequestCancelScheduledMergeCommand(osc.commandline_git.GitObsCommand):
    """
    Cancel scheduled merge of pull requests
    """

    name = "cancel-scheduled-merge"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_index, pr_id in enumerate(pull_request_ids):
            print(f"Canceling scheduled merge of {pr_id}...")

            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            gitea_api.PullRequest.cancel_scheduled_merge(
                self.gitea_conn,
                owner,
                repo,
                number,
            )
