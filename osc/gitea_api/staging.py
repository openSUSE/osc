import os
from typing import Optional


class StagingPullRequestWrapper:
    BACKLOG_LABEL = "staging/Backlog"
    INPROGRESS_LABEL = "staging/In Progress"

    def __init__(self, conn, owner: str, repo: str, number: int, *, topdir: str, cache_directory: Optional[str] = None):
        from . import PullRequest

        self.conn = conn
        self.owner = owner
        self.repo = repo
        self.number = number
        self._topdir = topdir
        self._cache_directory = cache_directory

        self.pr_obj = PullRequest.get(conn, owner, repo, number)
        self.git = None
        self.submodules_by_owner_repo = {}  # (owner, repo) -> submodule metadata; owner, repo must be lower case (Gitea is case insensitive)
        self.package_pr_map = {}  # (owner, repo, number) -> StagingPullRequestWrapper; owner, repo must be lower case (Gitea is case insensitive)

        self.base_git = None
        self.base_submodules_by_owner_repo = {}

    def clone(self):
        from . import Git
        from . import Repo

        path = os.path.join(self._topdir, f"{self.owner}_{self.repo}_{self.number}")
        Repo.clone_or_update(
            self.conn,
            self.owner,
            self.repo,
            pr_number=self.number,
            commit=self.pr_obj.head_commit,
            directory=path,
            cache_directory=self._cache_directory,
            depth=1,
            ssh_private_key_path=self.conn.login.ssh_key,
        )
        self.git = Git(path)

        submodules = self.git.get_submodules()
        self.submodules_by_owner_repo = dict([((i["owner"].lower(), i["repo"].lower()), i) for i in submodules.values()])

        for pkg_owner, pkg_repo, pkg_number in self.pr_obj.parse_pr_references():
            pkg_pr_obj = self.__class__(self.conn, pkg_owner, pkg_repo, pkg_number, topdir=self._topdir)
            self.package_pr_map[(pkg_owner.lower(), pkg_repo.lower(), pkg_number)] = pkg_pr_obj
            # FIXME: doesn't work when the commits are padded with zeros
            # assert self.submodules_by_owner_repo[(pkg_owner.lower(), pkg_repo.lower())]["commit"] == pkg_pr_obj.pr_obj.head_commit

    def clone_base(self):
        from . import Git
        from . import Repo

        path = os.path.join(self._topdir, f"{self.owner}_{self.repo}_{self.number}_base")
        Repo.clone_or_update(
            self.conn,
            self.owner,
            self.repo,
            branch=self.pr_obj.base_branch,
            commit=self.pr_obj.base_commit,
            directory=path,
            cache_directory=self._cache_directory,
            depth=1,
            ssh_private_key_path=self.conn.login.ssh_key,
        )
        self.base_git = Git(path)

        submodules = self.base_git.get_submodules()
        self.base_submodules_by_owner_repo = dict([((i["owner"].lower(), i["repo"].lower()), i) for i in submodules.values()])

    def merge(self, other):
        """
        Merge ``other`` pull request into ``self`` by MOVING all ``PR: <pr_id>`` references.
        It is crucial to remove the references from the original ``other`` request, otherwise the bots might get confused and close the pull request with reparented package pull request.
        """
        from . import Git
        from . import GitDiffGenerator
        from . import PullRequest

        self.pr_obj._data["body"] = PullRequest.add_pr_references(self.pr_obj.body, other.package_pr_map.keys())
        other.pr_obj._data["body"] = PullRequest.remove_pr_references(other.pr_obj.body, other.package_pr_map.keys())

        self_diff = GitDiffGenerator()
        self_diff._gitmodules.read(os.path.join(self.git.abspath, ".gitmodules"))
        other_diff = GitDiffGenerator()
        other_diff._gitmodules.read(os.path.join(other.git.abspath, ".gitmodules"))

        submodule_paths = []

        for pkg_owner, pkg_repo, pkg_number in other.package_pr_map:
            self_submodule = self.submodules_by_owner_repo.get((pkg_owner.lower(), pkg_repo.lower()), None)
            other_submodule = other.submodules_by_owner_repo.get((pkg_owner.lower(), pkg_repo.lower()), None)
            assert self_submodule or other_submodule

            if self_submodule:
                # use an existing path if the submodule already exists
                submodule_path = self_submodule["path"]
                submodule_branch = self_submodule["branch"]
            else:
                # use submodule path from the ``other`` pull request
                submodule_path = other_submodule["path"]
                submodule_branch = other_submodule["branch"]

            if self_submodule:
                self_diff.set_submodule_commit(submodule_path, self_submodule["commit"])
            if other_submodule:
                other_diff.set_submodule_commit(submodule_path, other_submodule["commit"])

            submodule_paths.append(submodule_path)

        if submodule_paths:
            import subprocess

            with subprocess.Popen(["git", "apply", "--index", "-"], encoding="utf-8", stdin=subprocess.PIPE, cwd=self.git.abspath) as proc:
                proc.communicate("\n".join(self_diff.diff(other_diff)))

            self.git.add(submodule_paths)
            self.git.commit(f"Merge package submodules from {other.pr_obj.base_owner}/{other.pr_obj.base_repo}!{other.pr_obj.number}")

    def remove(self, package_pr):
        """
        Remove a package submodule from this project.
        """
        from . import Git
        from . import GitObsRuntimeError
        from . import PullRequest

        self.pr_obj._data["body"] = PullRequest.remove_pr_references(self.pr_obj.body, [(package_pr.owner, package_pr.repo, package_pr.number)])

        submodule = self.submodules_by_owner_repo.get((package_pr.owner.lower(), package_pr.repo.lower()), None)
        base_submodule = self.base_submodules_by_owner_repo.get((package_pr.owner.lower(), package_pr.repo.lower()), None)

        if not submodule:
            raise GitObsRuntimeError(f"Unable to find a submodule for pull request {package_pr.owner}/{package_pr.repo}!{package_pr.number}")

        submodule_path = submodule["path"]

        if base_submodule:
            # we're reverting the submodule to an older commit
            self.git._run_git(["submodule", "update", "--init", "--remote", submodule_path])
            submodule_git = Git(os.path.join(self.git.abspath, submodule_path))
            submodule_git.reset(commit=base_submodule["commit"], hard=True)
            self.git.add([submodule_path])
        else:
            # we're removing the submodule completely
            self.git._run_git(["rm", submodule["path"]])

        self.git.commit(f"Remove package pull request {package_pr.pr_obj.base_owner}/{package_pr.pr_obj.base_repo}!{package_pr.pr_obj.number}")
