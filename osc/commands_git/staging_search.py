import sys

import osc.commandline_git


class StagingSearchCommand(osc.commandline_git.GitObsCommand):
    """
    Search staging pull requests.
    """

    name = "search"
    parent = "StagingCommand"

    def init_arguments(self):
        self.add_argument_owner_repo()
        self.add_argument(
            "--type",
            dest="type",
            # the choices must match the *_LABEL constants in StagingPullRequestWrapper class
            choices=("BACKLOG", "INPROGRESS", "ONHOLD"),
            required=True,
            help="Filter by review state.",
        )
        self.add_argument(
            "--package-review-state",
            dest="package_review_state",
            choices=("APPROVED", "ALL"),
            default="APPROVED",
            help="Filter by review state on *all* referenced *package* PRs.",
        )
        self.add_argument(
            "--export",
            action="store_true",
            help="Show json objects instead of human readable text",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.output import KeyValueTable
        from osc.output import tty

        self.print_gitea_settings()

        pr_state = "open"
        owner, repo = args.owner_repo

        labels = gitea_api.Repo.get_label_ids(self.gitea_conn, owner, repo)

        label = getattr(gitea_api.StagingPullRequestWrapper, f"{args.type}_LABEL")
        label_id = labels.get(label, None)
        if label_id is None:
            raise gitea_api.GitObsRuntimeError(f"Label '{label}' doesn't exist in '{owner}/{repo}'")

        pr_obj_list = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=pr_state, labels=[label_id])
        pr_obj_list.sort()

        table = KeyValueTable()
        result = []
        skipped = []
        for pr in pr_obj_list:
            ref_prs = pr.parse_pr_references()
            if len(ref_prs) == 0:
                skipped.append(pr)
                continue

            package_review_state_matched = True

            if args.package_review_state != "ALL":
                for ref_owner, ref_repo, ref_pr_number in ref_prs:
                    ref_pr = gitea_api.PullRequest.get(self.gitea_conn, ref_owner, ref_repo, ref_pr_number)

                    all_reviews = ref_pr.get_reviews(self.gitea_conn)
                    for review_obj in all_reviews:
                        if review_obj.state != args.package_review_state:
                            package_review_state_matched = False
                            break

                    if not package_review_state_matched:
                        break

            if package_review_state_matched:
                if args.export:
                    result.append(pr.dict())
                else:
                    table.add(pr.id, pr.title)
                    table.add("", pr.url)

        if args.export:
            from json import dumps

            print(dumps(result, indent=4, sort_keys=True))
        else:
            print(str(table))

        # print warnings at the end to make them more obvious
        if skipped:
            print(file=sys.stderr)
            for pr_obj in skipped:
                print(f"{tty.colorize('WARNING', 'yellow,bold')}: Skipped '{pr_obj.id}' due to empty or invalid 'PR:' references.", file=sys.stderr)
