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
            "--label",
            dest="labels",
            action="append",
            help="Filter by label. Can be specified multiple times.",
        )
        self.add_argument(
            "--export",
            action="store_true",
            help="Show json objects instead of human readable text",
        )

    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        total_entries = 0
        result = []
        for owner, repo in args.owner_repo:
            pr_obj_list = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=args.state)

            if args.no_draft:
                pr_obj_list = [i for i in pr_obj_list if not i.draft]

            if args.labels:
                # keep pull requests that contain at least one specified label
                specified_labels = set(args.labels)
                pr_obj_list = [pr for pr in pr_obj_list if not specified_labels.isdisjoint(pr.labels)]

            if args.target_branches:
                pr_obj_list = [i for i in pr_obj_list if i.base_branch in args.target_branches]

            if args.reviewers:
                review_states = args.review_states or ["REQUEST_REVIEW"]
                new_pr_obj_list = []
                for pr_obj in pr_obj_list:
                    all_reviews = pr_obj.get_reviews(self.gitea_conn)
                    user_reviews = {i.user: i.state for i in all_reviews if i.user and i.state in review_states}
                    team_reviews = {i.team: i.state for i in all_reviews if i.team and i.state in review_states}

                    user_reviewers = [i for i in args.reviewers if not i.startswith("@")]
                    team_reviewers = [i[1:] for i in args.reviewers if i.startswith("@")]

                    if set(user_reviews) & set(user_reviewers) or set(team_reviews) & set(team_reviewers):
                        new_pr_obj_list.append(pr_obj)

                pr_obj_list = new_pr_obj_list

            if pr_obj_list:
                total_entries += len(pr_obj_list)
                pr_obj_list.sort()
                if not args.export:
                    for pr_obj in pr_obj_list:
                        print(pr_obj.to_human_readable_string())
                        print()
                else:
                    repos_list = []
                    for pr_obj in pr_obj_list:
                        # we group results by owner and repo anyway, so exclude those columns from dicts to avoid data duplication
                        repos_list.append(pr_obj.dict(exclude_columns=["owner", "repo"]))
                    row = {"owner": owner, "repo": repo, "requests": repos_list}
                    result.append(row)

        if args.export:
            from json import dumps

            print(dumps(result, indent=4, sort_keys=True))

        print(f"Total entries: {total_entries}", file=sys.stderr)
