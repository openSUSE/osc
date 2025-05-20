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

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        total_entries = 0
        for owner, repo in args.owner_repo:
            data = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=args.state).json()

            if args.no_draft:
                data = [i for i in data if not i["draft"]]

            if args.target_branches:
                data = [i for i in data if i["base"]["ref"] in args.target_branches]

            review_states = args.review_states or ["REQUEST_REVIEW"]

            if args.reviewers:
                new_data = []
                for entry in data:
                    all_reviews = gitea_api.PullRequest.get_reviews(self.gitea_conn, owner, repo, entry["number"]).json()
                    user_reviews = {i["user"]["login"]: i["state"] for i in all_reviews if i["user"] and i["state"] in review_states}
                    team_reviews = {i["team"]["name"]: i["state"] for i in all_reviews if i["team"] and i["state"] in review_states}

                    user_reviewers = [i for i in args.reviewers if not i.startswith("@")]
                    team_reviewers = [i[1:] for i in args.reviewers if i.startswith("@")]

                    if set(user_reviews) & set(user_reviewers) or set(team_reviews) & set(team_reviewers):
                        print(set(user_reviews) & set(user_reviewers), set(team_reviews) & set(team_reviewers))
                        new_data.append(entry)

                data = new_data

            total_entries += len(data)

            text = gitea_api.PullRequest.list_to_human_readable_string(data, sort=True)
            if text:
                print(text)
                print("", file=sys.stderr)

        print(f"Total entries: {total_entries}", file=sys.stderr)
