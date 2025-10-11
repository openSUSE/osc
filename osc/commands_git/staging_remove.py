import sys
import osc.commandline_git
import re
from typing import List, Tuple
import os
from osc.gitea_api.utilities.git_utilities import GitUtilities as git_utilities
from osc import gitea_api
from osc.output import tty

BACKLOG_LABEL = "staging_backlog"
INPROGRESS_LABEL = "staging_inprogress"

class StagingRemoveCommand(osc.commandline_git.GitObsCommand):
    """
    Remove a pull request from a grouped staging PR.
    """
    name = "remove"
    aliases = []
    parent = "StagingCommand"

    def init_arguments(self):
        self.add_argument_owner_repo_pull(dest="pr_list", nargs="+").completer = osc.commandline_git.complete_pr
        self.add_argument('--workdir', required=True, help="Working directory for git operations.")
        self.add_argument('--grouped-pr', dest="grouped_pr", required=True, help="An existing grouped PR to update (e.g., owner/repo#number).")

    def _parse_grouped_pr(self, grouped_pr_identifier: str) -> dict:
        """Fetches and parses the grouped PR to build context and mappings."""

        context = {
            "grouped_pr_obj": None,
            "fwd_to_package": {},
            "package_to_fwd": {}
        }
        
        try:
            owner, repo, number = gitea_api.PullRequest.split_id(grouped_pr_identifier)
            grouped_pr_obj = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, number)
            context["grouped_pr_obj"] = grouped_pr_obj

            closes_refs = re.findall(r"^Closes: *(.*)$", grouped_pr_obj.body, re.M)
            if not closes_refs:
                print(f"{tty.colorize('ERROR', 'red,bold')}: PR '{grouped_pr_identifier}' contains no 'Closes:' references.", file=sys.stderr)
                sys.exit(1)

            for ref in closes_refs:
                fwd_pr_str, pkg_pr_str = ref.replace(')', '').split(' (')
                fwd_tuple = gitea_api.PullRequest.split_id(fwd_pr_str)
                pkg_tuple = gitea_api.PullRequest.split_id(pkg_pr_str)
                context["fwd_to_package"].setdefault(fwd_tuple, []).append(pkg_tuple)
                context["package_to_fwd"][pkg_tuple] = fwd_tuple
        except (gitea_api.GiteaException, ValueError) as e:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Failed to parse grouped PR '{grouped_pr_identifier}': {e}", file=sys.stderr)
            sys.exit(1)
        
        return context

    def _determine_prs_to_remove(self, pr_list: list, context: dict) -> List[Tuple[str, str, int]]:
        """Resolves user input to a unique list of forwarded PRs to remove."""
        
        fwd_prs_to_remove = set()
        for pr_tuple in pr_list:
            if pr_tuple in context["fwd_to_package"]:
                fwd_prs_to_remove.add(pr_tuple)
            elif pr_tuple in context["package_to_fwd"]:
                fwd_prs_to_remove.add(context["package_to_fwd"][pr_tuple])
            else:
                owner, repo, pull = pr_tuple
                print(f"{tty.colorize('ERROR', 'red,bold')}: PR '{owner}/{repo}#{pull}' is not in the grouped PR.", file=sys.stderr)
                sys.exit(1)
        
        return list(fwd_prs_to_remove)

    def _prepare_workspace(self, workdir: str, grouped_pr_obj) -> 'gitea_api.Git':
        """Clones the repository and checks out the correct branch."""

        clone_dir = os.path.join(workdir, f"{grouped_pr_obj.base_owner}_{grouped_pr_obj.base_repo}_{grouped_pr_obj.base_branch}")
        print(f"Using working directory: {clone_dir}")
        git_utilities.clone_or_update(grouped_pr_obj.base_owner, grouped_pr_obj.base_repo, branch=grouped_pr_obj.base_branch, directory=clone_dir)
        
        git = gitea_api.Git(clone_dir)
        git.reset(hard=True)
        git.checkout(grouped_pr_obj.head_branch)
        return git

    def _remove_submodules(self, git: 'gitea_api.Git', fwd_prs_to_remove: list, context: dict):
        """Removes submodules, commits the changes, and pushes to the remote."""
        grouped_pr_obj = context["grouped_pr_obj"]
        
        for fwd_pr in fwd_prs_to_remove:
            owner, repo, pull = fwd_pr
            print(f"Removing forwarded PR {owner}/{repo}#{pull}")
            packages_to_remove = context["fwd_to_package"].get(fwd_pr, [])
            for _, pkg_repo, _ in packages_to_remove:
                print(f" * Removing submodule '{pkg_repo}'")
                git.submodule_remove(pkg_repo, force=True, cached=True)
                git.submodule_config_remove(pkg_repo)

        git.add([".gitmodules"])

        removed_refs_str = '\n'.join([f"- {org}/{repo}!{num}" for org, repo, num in fwd_prs_to_remove])
        commit_message = f"Unstage PRs from grouped PR\n\nRemoved:\n{removed_refs_str}"
        git.commit(commit_message)
        git.push(remote="origin", branch=grouped_pr_obj.head_branch)

    def _update_gitea_state(self, fwd_prs_to_remove: list, context: dict):
        """Reopens removed PRs and updates the grouped PR's description."""
        
        grouped_pr_obj = context["grouped_pr_obj"]
        
        # Reopen removed forwarded PRs and update the tracking dictionary
        for fwd_pr in fwd_prs_to_remove:
            owner, repo, pull = fwd_pr
            gitea_api.PullRequest.reopen(self.gitea_conn, owner, repo, pull)
            context["fwd_to_package"].pop(fwd_pr, None)
        
        # Rebuild the description for the grouped PR
        pr_references = ""
        closes_references = ""
        for fwd_pr_tuple, pkg_prs_list in sorted(context["fwd_to_package"].items()):
            fwd_owner, fwd_repo, fwd_num = fwd_pr_tuple
            for pkg_owner, pkg_repo, pkg_num in pkg_prs_list:
                pr_references += f"PR: {pkg_owner}/{pkg_repo}!{pkg_num}\n"
                closes_references += f"Closes: {fwd_owner}/{fwd_repo}!{fwd_num} ({pkg_owner}/{pkg_repo}!{pkg_num})\n"
        
        new_description = f"{pr_references.strip()}\n\n{closes_references.strip()}"
        
        print(f"Updating description for PR {grouped_pr_obj.id}")
        gitea_api.PullRequest.set(
            self.gitea_conn, grouped_pr_obj.base_owner, grouped_pr_obj.base_repo, grouped_pr_obj.number,
            description=new_description
        )

    def run(self, args):
        self.print_gitea_settings()

        # 1. Parse the Grouped PR
        context = self._parse_grouped_pr(args.grouped_pr)

        # 2. Determine PRs to Remove
        fwd_prs_to_remove = self._determine_prs_to_remove(args.pr_list, context)
        if not fwd_prs_to_remove:
            print("No valid PRs found to remove. Exiting.")
            return

        # 3. Prepare Workspace
        git = self._prepare_workspace(args.workdir, context["grouped_pr_obj"])
        
        # 4. Perform Git Operations
        self._remove_submodules(git, fwd_prs_to_remove, context)

        # 5. Update Gitea State
        self._update_gitea_state(fwd_prs_to_remove, context)
        
        print("\nStaging remove process completed successfully.")