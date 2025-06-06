import osc.commandline_git


class PullRequestMergeCommand(osc.commandline_git.GitObsCommand):
    """
    Merge pull requests
    """

    name = "merge"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "id",
            nargs="+",
            help="Pull request ID in <owner>/<repo>#<number> format",
        )
        self.add_argument(
            "--now",
            action="store_true",
            help="Merge immediately, don't wait until all checks succeed.",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        pull_request_ids = args.id

        for pr_index, pr_id in enumerate(pull_request_ids):
            self.print_gitea_settings()

            print(f"Merging {pr_id}...")

            owner, repo, number = gitea_api.PullRequest.split_id(pr_id)
            gitea_api.PullRequest.merge(
                self.gitea_conn,
                owner,
                repo,
                number,
                merge_when_checks_succeed=not args.now,
            )
