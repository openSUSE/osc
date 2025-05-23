import sys

import osc.commandline_git


class PullRequestSearchCommand(osc.commandline_git.GitObsCommand):
    """
    Search pull requests in the whole gitea instance
    """

    name = "search"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument(
            "--state",
            choices=["open", "closed"],
            default="open",
            help="Filter by state: open, closed (default: open)",
        )
        self.add_argument(
            "--title",
            help="Filter by substring in title",
        )
        self.add_argument(
            "--owner",
            help="Filter by owner of the repository associated with the pull requests",
        )
        self.add_argument(
            "--label",
            dest="labels",
            metavar="LABEL",
            action="append",
            help="Filter by associated labels. Non existent labels are discarded. Can be specified multiple times.",
        )
        self.add_argument(
            "--assigned",
            action="store_true",
            help="Filter pull requests assigned to you",
        )
        self.add_argument(
            "--created",
            action="store_true",
            help="Filter pull requests created by you",
        )
        self.add_argument(
            "--mentioned",
            action="store_true",
            help="Filter pull requests mentioning you",
        )
        self.add_argument(
            "--review-requested",
            action="store_true",
            help="Filter pull requests requesting your review",
        )
        self.add_argument(
            "--export",
            action="store_true",
            help="Show json objects instead of human readable text",
        )


    def run(self, args):
        from osc import gitea_api

        self.print_gitea_settings()

        pr_obj_list = gitea_api.PullRequest.search(
            self.gitea_conn,
            state=args.state,
            title=args.title,
            owner=args.owner,
            labels=args.labels,
            assigned=args.assigned,
            created=args.created,
            mentioned=args.mentioned,
            review_requested=args.review_requested,
        )

        result = []
        if pr_obj_list:
            pr_obj_list.sort()
            for pr_obj in pr_obj_list:
                if not args.export:
                    print(pr_obj.to_human_readable_string())
                    print()
                else:
                    result.append(pr_obj.dict())

        if args.export:
            from json import dumps

            print(dumps(result, indent=4, sort_keys=True))

        print(f"Total entries: {len(pr_obj_list)}", file=sys.stderr)
