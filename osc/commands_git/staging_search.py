import osc.commandline_git
from ..gitea_api.staging import StagingPullRequestWrapper

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
            choices=("BACKLOG", "PROGRESS", "HOLD"),
            help="Filter by review state.",
        )               
        self.add_argument(
            "--review-state",
            dest="review_state",
            choices=("APPROVED", "ALL"),
            help="Filter by review state on the package PRs.",
        )
    
    def run(self, args):
        from osc import gitea_api
        
        self.print_gitea_settings()
            
        pr_state = "open"
        total_entries = 0
        result = []
        owner, repo = args.owner_repo
        
        labels = gitea_api.Repo.get_label_ids(self.gitea_conn, owner, repo)
        
        if args.type == "BACKLOG":
            label_id = labels.get(StagingPullRequestWrapper.BACKLOG_LABEL)
        elif args.type == "PROGRESS":
            label_id = labels.get(StagingPullRequestWrapper.INPROGRESS_LABEL)
        elif args.type == "HOLD":
            label_id = labels.get(StagingPullRequestWrapper.ONHOLD_LABEL)
        
        if not label_id:
             self.parser.error("Please specify --type option.")
             
        pr_obj_list = gitea_api.PullRequest.list(self.gitea_conn, owner, repo, state=pr_state, labels=[label_id])

        for pr in pr_obj_list:
            ref_prs = pr.parse_pr_references()
            if len(ref_prs) == 0:
                print("Skipping PR", pr.id, "due to empty or invalid PR references.")
                continue
            
            review_state = "APPROVED" if args.review_state is None else args.review_state
            review_state_matched = True

            for ref_owner, ref_repo, ref_pr_id in ref_prs:
                ref_pr = gitea_api.PullRequest.get(self.gitea_conn, ref_owner, ref_repo, ref_pr_id)

                all_reviews = ref_pr.get_reviews(self.gitea_conn)
                
                if review_state != "ALL":
                    for r in all_reviews:
                        if r.state !=  review_state:
                            review_state_matched = False
                            break 
                        
                if review_state_matched is False:
                    break
                
            if review_state_matched:
                print(f"******* \x1b]8;;{self.gitea_login.url}/{owner}/{repo}/pulls/{pr.number}\x1b\\{pr.id}\x1b]8;;\x1b\\: {pr.title}")