import sys
import osc.commandline_git

import re
from typing import List, Tuple, Optional
import os

## debugging
from IPython import embed
import pprint

from osc.gitea_api.utilities.git_utilities import GitUtilities as git_utilities

#from gitea_api import Git

BACKLOG_LABEL = "staging_backlog"
INPROGRESS_LABEL = "staging_inprogress"

class StagingCommandGroup(osc.commandline_git.GitObsCommand):
    """
    Group together staging pull requests
    """

    name = "group"
    aliases = []  # for compatibility with osc
    parent = "StagingCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_pr

        self.add_argument_owner_repo_pull(dest="prs", nargs="+").completer = complete_pr
        self.add_argument('--title', required=True, help="The new title for the staging PR.")
        self.add_argument('--branch', required=False, help="The branch to use for the staging PR.")
        self.add_argument('--workdir', required=True, help="Working directory for git operations.")
        self.add_argument('--force', required=False, help="Force the operation.", action='store_true')
        self.add_argument('--grouped-pr', dest="grouped_pr", required=False, help="An existing grouped PR to update (e.g., owner/repo#number).")
        #self.add_argument_owner_repo_pull(dest="--grouped-pr", required=False, nargs="+").completer = complete_pr
    
    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()

        #pr_obj._data['labels'] 
        num_entries = 0
        failed_entries = []
        prj_pkg_prs = []
        all_pkg_prs : List[Tuple[str, str, int]] = []  

        base_branch = None
        base_owner = None
        base_repo = None
        existing_pr_obj = None
        
        if args.grouped_pr:
            if args.branch is not None:
                print(f"{tty.colorize('ERROR', 'red,bold')}: --branch cannot be used together with --grouped-pr", file=sys.stderr)
                sys.exit(1)

            try:
                owner, repo, number = gitea_api.PullRequest.split_id(args.grouped_pr)
                existing_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)

                # Extract existing package and project references from the body
                all_pkg_prs.extend(existing_pr_obj.parse_pr_references())
                
                # Use a regex to find all "Closes: ..." lines
                closes_refs = re.findall(r"^Closes: *(.*)$", existing_pr_obj.body, re.M)
                prj_pkg_prs.extend(closes_refs)

                base_branch = existing_pr_obj.base_branch
                base_owner = existing_pr_obj.base_owner
                base_repo = existing_pr_obj.base_repo
                args.branch = existing_pr_obj.head_branch # Use the existing PR's branch
                args.title = existing_pr_obj.title # Keep the existing title

                print(f"Updating existing grouped PR: {args.grouped_pr}")
                #sys.exit(0)
            except (gitea_api.GiteaException, ValueError) as e:
                print(f"{tty.colorize('ERROR', 'red,bold')}: Failed to get or parse grouped PR '{args.grouped_pr}': {e}", file=sys.stderr)
                sys.exit(1)
        else:
            if args.branch is None:
                print(f"{tty.colorize('ERROR', 'red,bold')}: --branch is required if --grouped-pr is not used", file=sys.stderr)
                sys.exit(1)
                
                
        # Get package pull requests
        for owner, repo, pull in args.prs:
            try:
                pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, int(pull))
                
                #embed()
                
                if base_branch is None and base_owner is None and base_repo is None:
                    base_branch = pr_obj.base_branch
                    base_owner = owner
                    base_repo = repo
                elif base_branch != pr_obj.base_branch or base_owner != owner or base_repo != repo:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: All pull requests must target the same base branch and repository. Found differing base branch or repository in {owner}/{repo}#{pull}", file=sys.stderr)
                    sys.exit(1)
                
                if BACKLOG_LABEL not in pr_obj.labels and not args.force:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: Pull request {owner}/{repo}#{pull} does not have the '{BACKLOG_LABEL}' label.", file=sys.stderr)
                    sys.exit(1)
                                                    
                pkg_prs = pr_obj.parse_pr_references()
                
                if not pkg_prs:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: Couldn't find any package references in pull request {owner}/{repo}#{pull}", file=sys.stderr)
                    sys.exit(1)
                    
                all_pkg_prs.extend(pkg_prs)
                
                for pkg_pr_owner, pkg_pr_repo, pkg_pr_num in pkg_prs:
                    prj_pkg_prs.append(f"{owner}/{repo}!{pull} ({pkg_pr_owner}/{pkg_pr_repo}!{pkg_pr_num})")
                    
                
                pkg_prs_str = ', '.join(f"{org}/{repo}!{num}" for org, repo, num in pkg_prs)                
                print(f"Pull request {owner}/{repo}#{pull} references packages: {pkg_prs_str}")  
                
                #pprint.pprint(vars(pr_obj))
                #embed()
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(f"{owner}/{repo}#{pull}")
                    continue
                raise
        
        print(f"Target base branch: {base_branch}")
        # Setup working directory
        if not os.path.exists(args.workdir):
            print(f"{tty.colorize('ERROR', 'red,bold')}: Working directory '{args.workdir}' does not exist.", file=sys.stderr)
            sys.exit(1)
            
        clone_dir = os.path.join(args.workdir, f"{base_owner}_{base_repo}_{base_branch}")
        print(f"Using working directory: {clone_dir}")
        git_utilities.clone_or_update(base_owner, base_repo,  branch=base_branch, directory=clone_dir)
        git = gitea_api.Git(clone_dir)

        for owner, repo, pull in all_pkg_prs:
            try:
                pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, int(pull))
                print(f"Processing pull request {owner}/{repo}#{pull}")
                print(f"{pr_obj.head_branch}-{pr_obj.head_commit} -> {pr_obj.base_branch}")
                                
                submod_status = git_utilities.is_submodule(git, clone_dir, repo)
                    
                if submod_status:       
                    if submod_status.startswith('-'):
                        # submodule is not initialized, initialize it
                        git.submodule_update(repo, init=True)       
                              
                    # Fetch and checkout the pull request in the submodule
                    gitsm = gitea_api.Git(os.path.join(clone_dir, repo))
                    
                    gitsm.reset()
                    # checkout the pull request and check if HEAD matches head/sha from Gitea
                    pr_branch = gitsm.fetch_pull_request(pull, commit=pr_obj.head_commit, force=True)
  
                    gitsm.switch(pr_branch)         
                else:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: {repo} submodule does not exist.", file=sys.stderr)
                    sys.exit(1)

            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(f"{owner}/{repo}#{pull}")
                    continue
                raise        
            
        repos = [repo for _, repo, _ in all_pkg_prs]   
        git.add(repos)
        if git.has_changes():
            message = '\n'.join([f"PR: {org}/{repo}!{num}" for org, repo, num in args.prs])
            
            pr_references = '\n'.join([f"PR: {org}/{repo}!{num}" for org, repo, num in all_pkg_prs])
            closes_references = '\n'.join([f"Closes: {pkg}" for pkg in prj_pkg_prs])
            description = f"{pr_references}\n\n{closes_references}"
                               
            if existing_pr_obj:
                if git.branch_exists(args.branch):
                    git.branch(args.branch, "origin/" + args.branch)
                    git.checkout(args.branch)
                    
                else:
                    git.checkout("origin/" + args.branch, track=True)
                
                git.commit(f"Update staging PR with new changes\n\n{message}")
                
                git.push(remote="origin", branch=args.branch, force=args.force)

                print(f"Updating description for PR {existing_pr_obj.id}")
                gitea_api.PullRequest.set(
                    self.gitea_conn,
                    base_owner, base_repo, existing_pr_obj.number,
                    description=description
                )
            else:
                if git.branch_exists(args.branch):
                    if not args.force:
                        print(f"{tty.colorize('ERROR', 'red,bold')}: Branch '{args.branch}' already exists in the repository {base_owner}/{base_repo}, please choose a different branch name.", file=sys.stderr)
                        sys.exit(1)
                    else:
                        # delete remote branch and its tracking 
                        git.delete_branch(args.branch, "origin", force=True)
                        git.delete_branch(args.branch, force=True)
                        
                    #git.checkout(args.branch)
                #else:   
                git.checkout(args.branch, create_new=True)
                
                git.commit(f"Creating staging PR {args.title}\n\n{message}")
                
                print(f"Pushing branch {args.branch} to origin")
                
                git.push(remote="origin", branch=args.branch, force=args.force)
                
                print(f"Creating pull request in {base_owner}/{base_repo}#{base_branch}")
                
                pr_obj = gitea_api.PullRequest.create(
                    self.gitea_conn,
                    target_owner=base_owner,
                    target_repo=base_repo,
                    target_branch=base_branch,
                    source_owner=base_owner,
                    # source_repo is not required because the information lives in Gitea database
                    source_branch=args.branch,
                    title=args.title,
                    description=description,
                )
                gitea_api.PullRequest.add_labels(self.gitea_conn, base_owner, base_repo, pr_obj.number, [INPROGRESS_LABEL])
                
                print(pr_obj.to_human_readable_string())

            
            # Remove backlog label from all backlog PRs and close them
            for owner, repo, pull in args.prs:
                try:
                    #gitea_api.PullRequest.remove_label(self.gitea_conn, owner, repo, int(pull), BACKLOG_LABEL)
                    gitea_api.PullRequest.close(self.gitea_conn, owner, repo, int(pull))
                except gitea_api.GiteaException as e:
                    if e.status == 404:
                        failed_entries.append(f"{owner}/{repo}#{pull}")
                        continue
                    raise                

        #print(f"Total entries: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(
                f"{tty.colorize('ERROR', 'red,bold')}: Couldn't retrieve the following pull requests: {', '.join(failed_entries)}",
                file=sys.stderr,
            )
            sys.exit(1)
