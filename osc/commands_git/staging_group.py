import sys
import osc.commandline_git

import re
from typing import List, Tuple, Optional
import os

## debugging
from IPython import embed
import pprint

#from gitea_api import Git

BACKLOG_LABEL = "backlog"

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
        self.add_argument('--branch', required=True, help="The branch to use for the staging PR.")
        self.add_argument('--workdir', required=True, help="Working directory for git operations.")
        self.add_argument('--force', required=False, help="Force the operation.", action='store_true')
    
    def clone_or_update(
        self,
        owner: str,
        repo: str,
        *,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
        directory: str,
        reference: Optional[str] = None,
    ):
        from osc import gitea_api

        if not pr_number and not branch:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")

        if not os.path.exists(os.path.join(directory, ".git")):
            gitea_api.Repo.clone(
                self.gitea_conn,
                owner,
                repo,
                directory=directory,
                add_remotes=True,
                reference=reference,
            )

        git = gitea_api.Git(directory)
        git_owner, git_repo = git.get_owner_repo()
        assert git_owner == owner, f"owner does not match: {git_owner} != {owner}"
        assert git_repo == repo, f"repo does not match: {git_repo} != {repo}"

        if pr_number:
            # ``git reset`` is required for fetching the pull request into an existing branch correctly
            # without it, ``git submodule status`` is broken and returns old data
            git.reset()
            # checkout the pull request and check if HEAD matches head/sha from Gitea
            pr_branch = git.fetch_pull_request(pr_number, commit=commit, force=True)
            git.switch(pr_branch)
            head_commit = git.get_branch_head()
            assert (
                head_commit == commit
            ), f"HEAD of the current branch '{pr_branch}' is '{head_commit}' but the Gitea pull request points to '{commit}'"
        elif branch:
            git.switch(branch)

            if commit:
                # run 'git fetch' only when the branch head is different to the expected commit
                head_commit = git.get_branch_head()
                if head_commit != commit:
                    git.fetch()

                if not git.branch_contains_commit(commit=commit, remote="origin"):
                    raise RuntimeError(f"Branch '{branch}' doesn't contain commit '{commit}'")
                git.reset(commit, hard=True)
            else:   
                git.fetch()
        else:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")
        
        return git
    
    def is_submodule(self, git, repo_path: str, submodule_path: str) -> str:
        """
        Checks if a directory is a registered Git submodule.

        Args:
            git: An instance of the Git class representing the repository.
            repo_path: The absolute path to the main repository.
            submodule_path: The relative path to the submodule from the repo root.

        Returns:
            True if the path is a registered submodule, False otherwise.
        """
        # Ensure the provided path exists and is a directory
        if not os.path.isdir(os.path.join(repo_path, submodule_path)):
            print(f"  Path '{submodule_path}' does not exist or is not a directory.")
            return None

        
        return git.submodule_status(submodule_path)
    
    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()

        #pr_obj._data['labels'] 
        num_entries = 0
        failed_entries = []
        all_pkg_prs : List[Tuple[str, str, int]] = []  

        base_branch = None
        base_owner = None
        base_repo = None
        
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
                    print(f"{tty.colorize('ERROR', 'red,bold')}: Pull request {owner}/{repo}#{pull} does not have the 'staging' label.", file=sys.stderr)
                    sys.exit(1)
                                                    
                pkg_prs = pr_obj.parse_pr_references()
                
                if not pkg_prs:
                    print(f"{tty.colorize('ERROR', 'red,bold')}: Couldn't find any package references in pull request {owner}/{repo}#{pull}", file=sys.stderr)
                    sys.exit(1)
                    
                all_pkg_prs.extend(pkg_prs)
                
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
        self.clone_or_update(base_owner, base_repo,  branch=base_branch, directory=clone_dir)
        git = gitea_api.Git(clone_dir)

        for owner, repo, pull in all_pkg_prs:
            try:
                pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, int(pull))
                print(f"Processing pull request {owner}/{repo}#{pull}")
                print(f"{pr_obj.head_branch}-{pr_obj.head_commit} -> {pr_obj.base_branch}")
                
                #breakpoint()
                
                submod_status = self.is_submodule(git, clone_dir, repo)
                
                if submod_status.startswith('-'):
                    # submodule is not initialized, initialize it
                    git.submodule_update(repo, init=True)
                    
                if submod_status:                    
                    print(f"  Updating submodule {repo}")
                    #os.chdir(os.path.join(clone_dir, repo))
                    gitsm = gitea_api.Git(os.path.join(clone_dir, repo))
                    
                    gitsm.reset()
                    # checkout the pull request and check if HEAD matches head/sha from Gitea
                    pr_branch = gitsm.fetch_pull_request(pull, commit=pr_obj.head_commit, force=True)
  
                    gitsm.switch(pr_branch)
                    
                else:
                    print(f"  Skipping {repo}, not a submodule")
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(f"{owner}/{repo}#{pull}")
                    continue
                raise        
            
        repos = [repo for _, repo, _ in all_pkg_prs]   
        git.add(repos)
        if git.has_changes():
            message = '\n'.join([f"PR: {org}/{repo}!{num}" for org, repo, num in all_pkg_prs])
            message =  message + "\n\n" + '\n'.join([f"Closes: {org}/{repo}!{num}" for org, repo, num in args.prs]) 

            print(f"Committing changes {message}")
            if git.branch_exists(args.branch):
                print(f"{tty.colorize('ERROR', 'red,bold')}: Branch '{args.branch}' already exists in the repository {base_owner}/{base_repo}, please choose a different branch name.", file=sys.stderr)
                sys.exit(1)
            
            git.checkout(args.branch, create_new=True)
            git.commit(f"Creating staging PR {args.title}\n\n{message}")
            
            print(f"Pushing branch {args.branch} to origin")
            git.push(remote="origin", branch=args.branch)
            
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
                description=message,
            )
            
            print(pr_obj.to_human_readable_string())
            
            # Remove backlog label from all backlog PRs and close them
            for owner, repo, pull in args.prs:
                try:
                    gitea_api.PullRequest.remove_label(self.gitea_conn, owner, repo, int(pull), BACKLOG_LABEL)
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
