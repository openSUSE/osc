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
        self.add_argument(
            "--reviewer",
            dest="reviewers",
            action="append",
            help="Filter by reviewer. Team reviewers start with '@'.",
        )
        self.add_argument(
            "--review-state",
            dest="review_states",
            action="append",
            choices=("REQUEST_REVIEW", "APPROVED"),
            help="Filter by review state. Needs to be used with ``--reviewer``.",
        )
        self.add_argument(
            "--target-branch",
            dest="target_branches",
            action="append",
            help="Filter by target branch.",
        )
        self.add_argument(
            "--no-draft",
            action="store_true",
            help="Filter by draft flag. Exclude pull requests with draft flag set.",
        )
        self.add_argument(
            "--format",
            choices=["text", "json"],
            default="text",
            help="Output format (default: open)",
        )
        self.add_argument(
            "--json",
            action="store_true",
            help="Print output in json",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.output.formatter_creator import FormatterCreator

        self.print_gitea_settings()

        formatter = FormatterCreator().formatter_from_args(args)
        formatter.start()

        total_entries = 0
        for owner, repo in args.owner_repo:
            pr_obj_list = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=args.state)

            if args.no_draft:
                pr_obj_list = [i for i in pr_obj_list if not i.draft]

            if args.target_branches:
                pr_obj_list = [i for i in pr_obj_list if i.base_branch in args.target_branches]

            if args.reviewers:
                review_states = args.review_states or ["REQUEST_REVIEW"]
                new_pr_obj_list = []
                for pr_obj in pr_obj_list:
                    all_reviews = gitea_api.PullRequest.get_reviews(self.gitea_conn, owner, repo, pr_obj.number).json()
                    user_reviews = {i["user"]["login"]: i["state"] for i in all_reviews if i["user"] and i["state"] in review_states}
                    team_reviews = {i["team"]["name"]: i["state"] for i in all_reviews if i["team"] and i["state"] in review_states}

                    user_reviewers = [i for i in args.reviewers if not i.startswith("@")]
                    team_reviewers = [i[1:] for i in args.reviewers if i.startswith("@")]

                    if set(user_reviews) & set(user_reviewers) or set(team_reviews) & set(team_reviewers):
                        new_pr_obj_list.append(pr_obj)

                pr_obj_list = new_pr_obj_list

            if pr_obj_list:
                total_entries += len(pr_obj_list)
                pr_obj_list.sort()
                formatter.format_list(pr_obj_list)

        formatter.finish(f"Total entries: {total_entries}")
