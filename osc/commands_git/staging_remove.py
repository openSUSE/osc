import sys
import osc.commandline_git

import re
from typing import List, Tuple
import os
from osc.gitea_api.utilities.git_utilities import GitUtilities as git_utilities

BACKLOG_LABEL = "staging_backlog"
INPROGRESS_LABEL = "staging_inprogress"

class StagingRemoveCommand(osc.commandline_git.GitObsCommand):
    """
    Group together staging pull requests
    """

    name = "remove"
    aliases = []  # for compatibility with osc
    parent = "StagingCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_pr

        self.add_argument_owner_repo_pull(dest="pr_list", nargs="+").completer = complete_pr
        self.add_argument('--workdir', required=True, help="Working directory for git operations.")
        self.add_argument('--grouped-pr', dest="grouped_pr", required=True, help="An existing grouped PR to update (e.g., owner/repo#number).")
    
    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty
    
        prj_pkg_prs = []
        all_pkg_prs : List[Tuple[str, str, int]] = []  
        
        fwd_to_package = {}
        package_to_fwd = {}

        try:
            owner, repo, number = gitea_api.PullRequest.split_id(args.grouped_pr)
            grouped_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)

            # Extract existing package and project references from the body
            all_pkg_prs.extend(grouped_pr_obj.parse_pr_references())
            
            # Use a regex to find all "Closes: ..." lines
            closes_refs = re.findall(r"^Closes: *(.*)$", grouped_pr_obj.body, re.M)
            
            if not closes_refs:
                print(f"{tty.colorize('ERROR', 'red,bold')}: The specified grouped PR '{args.grouped_pr}' does not contain any 'Closes: ...' references in its body.", file=sys.stderr)
                sys.exit(1)
                
            prj_pkg_prs.extend(closes_refs)

            for closed_ref in closes_refs:
                fwd_pr, pkg_pr = closed_ref.replace(')', '').split(' (')
                fwd_pr_tuple = gitea_api.PullRequest.split_id(fwd_pr)  
                pkg_pr_tuple = gitea_api.PullRequest.split_id(pkg_pr)
                if fwd_pr_tuple not in fwd_to_package:
                    fwd_to_package[fwd_pr_tuple] = []  
                fwd_to_package[fwd_pr_tuple].append(pkg_pr_tuple)
                package_to_fwd[pkg_pr_tuple] = fwd_pr_tuple
            
            base_branch = grouped_pr_obj.base_branch
            base_owner = grouped_pr_obj.base_owner
            base_repo = grouped_pr_obj.base_repo
            head_branch = grouped_pr_obj.head_branch 

        except (gitea_api.GiteaException, ValueError) as e:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Failed to get or parse grouped PR '{args.grouped_pr}': {e}", file=sys.stderr)
            sys.exit(1)
            
        fwd_prs_to_remove = []
        for pr in args.pr_list:
            owner,repo,pull = pr

            # the user can specify either the package PR or the forwarding PR            
            if fwd_to_package.get(pr):
                fwd_prs_to_remove.append(pr)
            else:
                fwd_pr = package_to_fwd.get(pr) 
                if fwd_pr:
                   fwd_prs_to_remove.append(fwd_pr)
                else:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: The specified PR '{owner}/{repo}#{pull}' is not referenced in the grouped PR '{args.grouped_pr}'. Skipping.", file=sys.stderr)
                    sys.exit(1)
          
        fwd_prs_to_remove = list(set(fwd_prs_to_remove))  # Remove duplicates          
        
        # Clone or update the base repository
        clone_dir = os.path.join(args.workdir, f"{base_owner}_{base_repo}_{base_branch}")
        print(f"Using working directory: {clone_dir}")
        git_utilities.clone_or_update(base_owner, base_repo,  branch=base_branch, directory=clone_dir)
        git = gitea_api.Git(clone_dir)
        git.reset(hard=True)
        git.checkout(head_branch)
                
        
        # Remove submodule entries for the specified PRs
        submodules = []
        for fwd_pr in fwd_prs_to_remove:
            owner, repo, pull = fwd_pr
            print(f"Removing pull request {owner}/{repo}#{pull}")   
            
            pkgs = fwd_to_package.get(fwd_pr)
            
            for owner, repo, pull in pkgs:  
                submod_status = git_utilities.is_submodule(git, clone_dir, repo)
                        
                if submod_status:            
                    print(f" * Removing submodule '{repo}'")
                    git.submodule_remove(repo, force=True, cached=True)
                    submodules.append(repo)
                else:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: '{repo}' is not a submodule in the working directory.", file=sys.stderr)
                    sys.exit(1)         
                    
        # moved here to avoid multiple commits when removing multiple submodules
        # please stage your changes to .gitmodules or stash them to proceed          
        for submodule in submodules:  
            git.submodule_config_remove(submodule)
        git.add([".gitmodules"])
        
        pr_references = ""
        for fwd_pr_to_remove in fwd_prs_to_remove:
            org, repo, num = fwd_pr_to_remove
            pkg_prs = fwd_to_package.get(fwd_pr_to_remove)
            for pkg_pr_org, pkg_pr_repo, pkg_pr_num in pkg_prs:
                pr_references += f"- {pkg_pr_org}/{pkg_pr_repo}!{pkg_pr_num} ({org}/{repo}!{num})"        
        
        message = f"Unstaged from grouped PR {args.grouped_pr} the following pull requests:\n\n{pr_references}"
        git.commit(message)
        git.push(remote="origin", branch=head_branch)
        
        # Reopen removed forwarded PR
        # update fwd_to_package 
        for fwd_pr in fwd_prs_to_remove:
            owner,repo,pull = fwd_pr
            gitea_api.PullRequest.reopen(self.gitea_conn, owner, repo, pull)
            fwd_to_package.pop(fwd_pr, None)

        
        # Update the grouped PR body
        pr_references = ""
        closes_references = ""
        for fwd_pr, pkg_prs in fwd_to_package.items():            
            for pkg_pr in pkg_prs:
                pr_references += f"PR: {pkg_pr[0]}/{pkg_pr[1]}#{pkg_pr[2]}\n"
                closes_references += f"Closes: {fwd_pr[0]}/{fwd_pr[1]}!{fwd_pr[2]} ({pkg_pr[0]}/{pkg_pr[1]}#{pkg_pr[2]})\n"
                
            
        message = f"{pr_references}\n\n{closes_references}"
        
        print(f"Updating description for PR {grouped_pr_obj.id}")
        try:
            gitea_api.PullRequest.set(
                self.gitea_conn,
                base_owner, base_repo, grouped_pr_obj.number,
                description=message
            )    
        except (gitea_api.GiteaException, ValueError) as e:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Failed to update grouped PR '{args.grouped_pr}': {e}", file=sys.stderr)
            sys.exit(1)
    
        
