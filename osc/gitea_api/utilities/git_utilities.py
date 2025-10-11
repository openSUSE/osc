import os
from typing import Optional

class GitUtilities:
    @staticmethod
    def clone_or_update(
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
    
    @staticmethod
    def is_submodule(git, repo_path: str, submodule_path: str) -> str:
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