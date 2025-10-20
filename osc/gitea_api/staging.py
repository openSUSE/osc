import os


class StagingPullRequestWrapper:
    BACKLOG_LABEL = "staging/Backlog"
    INPROGRESS_LABEL = "staging/In Progress"

    def __init__(self, conn, owner: str, repo: str, number: int, *, topdir: str):
        from . import PullRequest

        self.conn = conn
        self.owner = owner
        self.repo = repo
        self.number = number
        self._topdir = topdir

        self.pr_obj = PullRequest.get(conn, owner, repo, number)
        self.git = None
        self.submodules_by_owner_repo = {}
        self.package_pr_map = {}

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
            ssh_private_key_path=self.conn.login.ssh_key,
        )
        self.git = Git(path)
        # git fetch --all to have all commits from all remotes available
        self.git.fetch()

        submodules = self.git.get_submodules()
        self.submodules_by_owner_repo = dict([((i["owner"], i["repo"]), i) for i in submodules.values()])

        for pkg_owner, pkg_repo, pkg_number in self.pr_obj.parse_pr_references():
            pkg_pr_obj = self.__class__(self.conn, pkg_owner, pkg_repo, pkg_number, topdir=self._topdir)
            self.package_pr_map[(pkg_owner, pkg_repo, pkg_number)] = pkg_pr_obj
            # FIXME: doesn't work when the commits are padded with zeros
            # assert self.submodules_by_owner_repo[(pkg_owner, pkg_repo)]["commit"] == pkg_pr_obj.pr_obj.head_commit

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
            ssh_private_key_path=self.conn.login.ssh_key,
        )
        self.base_git = Git(path)
        # git fetch --all to have all commits from all remotes available
        self.base_git.fetch()

        submodules = self.base_git.get_submodules()
        self.base_submodules_by_owner_repo = dict([((i["owner"], i["repo"]), i) for i in submodules.values()])

    def merge(self, other):
        """
        Merge ``other`` pull request into ``self`` by MOVING all ``PR: <pr_id>`` references.
        It is crucial to remove the references from the self.package_pr_maporiginal ``other`` request, otherwise the bots might get confused and close the pull request with reparented package pull request.
        """
        from . import Git
        from . import PullRequest

        self.pr_obj._data["body"] = PullRequest.add_pr_references(self.pr_obj.body, other.package_pr_map.keys())
        other.pr_obj._data["body"] = PullRequest.remove_pr_references(other.pr_obj.body, other.package_pr_map.keys())

        submodule_paths = []

        for pkg_owner, pkg_repo, pkg_number in other.package_pr_map:
            other_submodule = other.submodules_by_owner_repo[(pkg_owner, pkg_repo)]
            self_submodule = self.submodules_by_owner_repo.get((pkg_owner, pkg_repo), None)

            if self_submodule:
                # use an existing path if the submodule already exists
                submodule_path = self_submodule["path"]
                submodule_branch = self_submodule["branch"]
            else:
                # use submodule path from the ``other`` pull request
                submodule_path = other_submodule["path"]
                submodule_branch = other_submodule["branch"]

            # add a submodule if missing
            if not self_submodule:
                self.git._run_git(["submodule", "add", "-b", submodule_branch, f"../../{pkg_owner}/{pkg_repo}", submodule_path])

            # init the submodule
            self.git._run_git(["submodule", "update", "--init", submodule_path])

            submodule_git = Git(os.path.join(self.git.abspath, submodule_path))
            submodule_git.fetch()
            submodule_git._run_git(["fetch", "origin", f"pull/{pkg_number}/head:{submodule_branch}", "--force", "--update-head-ok"])
            submodule_paths.append(submodule_path)

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

        submodule = self.submodules_by_owner_repo.get((package_pr.owner, package_pr.repo), None)
        base_submodule = self.base_submodules_by_owner_repo.get((package_pr.owner, package_pr.repo), None)

        if not submodule:
            raise GitObsRuntimeError(f"Unable to find a submodule for pull request {package_pr.owner}/{package_pr.repo}!{package_pr.number}")

        submodule_path = submodule["path"]

        if base_submodule:
            # we're reverting the submodule to an older commit
            self.git._run_git(["submodule", "update", "--init", "--remote", submodule_path])
            submodule_git = Git(os.path.join(self.git.abspath, submodule_path))
            submodule_git.fetch()
            submodule_git.reset(commit=base_submodule["commit"], hard=True)
            self.git.add([submodule_path])
        else:
            # we're removing the submodule completely
            self.git._run_git(["rm", submodule["path"]])

        self.git.commit(f"Remove package pull request {package_pr.pr_obj.base_owner}/{package_pr.pr_obj.base_repo}!{package_pr.pr_obj.number}")
