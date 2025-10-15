import functools
import os
import re
import subprocess
from typing import List
from typing import Optional
from typing import Tuple

from .common import GiteaModel
from .connection import Connection
from .connection import GiteaHTTPResponse
from .user import User


@functools.total_ordering
class Repo(GiteaModel):
    def __eq__(self, other):
        (self.owner, self.repo) == (other.owner, other.repo)

    def __lt__(self, other):
        (self.owner, self.repo) < (other.owner, other.repo)

    @property
    def owner(self) -> str:
        return self._data["owner"]["login"]

    @property
    def owner_obj(self) -> User:
        return User(self._data["owner"])

    @property
    def repo(self) -> str:
        return self._data["name"]

    @property
    def parent_obj(self) -> Optional["Repo"]:
        if not self._data["parent"]:
            return None
        return Repo(self._data["parent"])

    @property
    def clone_url(self) -> str:
        return self._data["clone_url"]

    @property
    def ssh_url(self) -> str:
        return self._data["ssh_url"]

    @property
    def default_branch(self) -> str:
        return self._data["default_branch"]

    @classmethod
    def split_id(cls, repo_id: str) -> Tuple[str, str]:
        """
        Split <owner>/<repo> into individual components and return them in a tuple.
        """
        match = re.match(r"^([^/]+)/([^/]+)$", repo_id)
        if not match:
            raise ValueError(f"Invalid repo id: {repo_id}")
        return match.group(1), match.group(2)

    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> "Repo":
        """
        Retrieve details about a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        url = conn.makeurl("repos", owner, repo)
        response = conn.request("GET", url)
        obj = cls(response.json(), response=response)
        return obj

    @classmethod
    def clone(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        branch: Optional[str] = None,
        quiet: bool = False,
        directory: Optional[str] = None,
        cwd: Optional[str] = None,
        use_http: bool = False,
        add_remotes: bool = False,
        reference: Optional[str] = None,
        reference_if_able: Optional[str] = None,
        ssh_private_key_path: Optional[str] = None,
        ssh_strict_host_key_checking: bool = True,
    ) -> str:
        """
        Clone a repository using 'git clone' command, return absolute path to it.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        :param directory: The name of a new directory to clone into. Defaults to the repo name.
        :param cwd: Working directory. Defaults to the current working directory.
        :param use_http: Whether to use``clone_url`` for cloning over http(s) instead of ``ssh_url`` for cloning over SSH.
        :param add_remotes: Determine and add 'parent' or 'fork' remotes to the cloned repo.
        :param reference: Reuse objects from the specified local repository, error out if the repository doesn't exist.
        :param reference_if_able: Reuse objects from the specified local repository, only print warning if the repository doesn't exist.
        """
        import shlex

        cwd = os.path.abspath(cwd) if cwd else os.getcwd()
        directory = directory if directory else repo
        # it's perfectly fine to use os.path.join() here because git can take an absolute path
        directory_abspath = os.path.join(cwd, directory)

        repo_obj = cls.get(conn, owner, repo)

        clone_url = repo_obj.clone_url if use_http else repo_obj.ssh_url

        remotes = {}
        if add_remotes:
            user_obj = User.get(conn)
            if repo_obj.owner == user_obj.login:
                # we're cloning our own repo, setting remote to the parent (if exists)
                if repo_obj.parent_obj:
                    remotes["parent"] = repo_obj.parent_obj.clone_url if use_http else repo_obj.parent_obj.ssh_url
            else:
                # we're cloning someone else's repo, setting remote to our fork (if exists)
                from . import Fork

                fork_obj_list = Fork.list(conn, owner, repo)
                fork_obj_list = [fork_obj for fork_obj in fork_obj_list if fork_obj.owner == user_obj.login]
                if fork_obj_list:
                    assert len(fork_obj_list) == 1
                    fork_obj = fork_obj_list[0]
                    remotes["fork"] = fork_obj.clone_url if use_http else fork_obj.ssh_url

        ssh_args = []
        env = os.environ.copy()

        if ssh_private_key_path and not use_http:
            ssh_args += [
                # avoid guessing the ssh key, use the specified one
                "-o IdentitiesOnly=yes",
                f"-o IdentityFile={shlex.quote(ssh_private_key_path)}",
            ]

        if not ssh_strict_host_key_checking:
            ssh_args += [
                "-o StrictHostKeyChecking=no",
                "-o UserKnownHostsFile=/dev/null",
                "-o LogLevel=ERROR",
            ]

        if ssh_args:
            env["GIT_SSH_COMMAND"] = f"ssh {' '.join(ssh_args)}"

        # clone
        cmd = ["git", "clone", clone_url, directory]

        if branch:
            cmd += ["--branch", branch]

        if reference:
            cmd += ["--reference", reference]

        if reference_if_able:
            cmd += ["--reference-if-able", reference_if_able]

        if quiet:
            cmd += ["--quiet"]

        subprocess.run(cmd, cwd=cwd, env=env, check=True)

        # setup remotes
        for name, url in remotes.items():
            cmd = ["git", "-C", directory_abspath, "remote", "add", name, url]
            subprocess.run(cmd, cwd=cwd, check=True)

        # store used ssh args (GIT_SSH_COMMAND) in the local git config
        # to allow seamlessly running ``git push`` and other commands
        if ssh_args:
            cmd = [
                "git",
                "-C",
                directory_abspath,
                "config",
                "core.sshCommand",
                f"echo 'Using core.sshCommand: {env['GIT_SSH_COMMAND']}' >&2; {env['GIT_SSH_COMMAND']}",
            ]
            subprocess.run(cmd, cwd=cwd, check=True)

        return directory_abspath

    @classmethod
    def clone_or_update(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        pr_number: Optional[int] = None,
        branch: Optional[str] = None,
        commit: Optional[str] = None,
        directory: str,
        reference: Optional[str] = None,
        remote: Optional[str] = None,
    ):
        from osc import gitea_api

        if not pr_number and not branch:
            raise ValueError("Either 'pr_number' or 'branch' must be specified")

        if not os.path.exists(os.path.join(directory, ".git")):
            gitea_api.Repo.clone(
                conn,
                owner,
                repo,
                directory=directory,
                add_remotes=True,
                reference=reference,
            )

        git = gitea_api.Git(directory)
        git_owner, git_repo = git.get_owner_repo(remote)
        assert git_owner.lower() == owner.lower(), f"owner does not match: {git_owner} != {owner}"
        assert git_repo.lower() == repo.lower(), f"repo does not match: {git_repo} != {repo}"

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

    @classmethod
    def list_org_repos(cls, conn: Connection, owner: str) -> List["Repo"]:
        """
        List repos owned by an organization.

        :param conn: Gitea ``Connection`` instance.
        """
        q = {
            # XXX: limit works in range 1..50, setting it any higher doesn't help, we need to handle paginated results
            "limit": 10**6,
        }
        url = conn.makeurl("orgs", owner, "repos", query=q)
        obj_list = []
        for response in conn.request_all_pages("GET", url):
            obj_list.extend([cls(i, response=response) for i in response.json()])
        return obj_list

    @classmethod
    def list_user_repos(cls, conn: Connection, owner: str) -> List["Repo"]:
        """
        List repos owned by a user.

        :param conn: Gitea ``Connection`` instance.
        """
        q = {
            # XXX: limit works in range 1..50, setting it any higher doesn't help, we need to handle paginated results
            "limit": 10**6,
        }
        url = conn.makeurl("users", owner, "repos", query=q)
        obj_list = []
        for response in conn.request_all_pages("GET", url):
            obj_list.extend([cls(i, response=response) for i in response.json()])
        return obj_list
