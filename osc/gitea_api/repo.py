import functools
import os
import re
import subprocess
from typing import List
from typing import Optional
from typing import Tuple

from .connection import Connection
from .connection import GiteaHTTPResponse
from .user import User


@functools.total_ordering
class Repo:
    def __init__(self, data: dict, *, response: Optional[GiteaHTTPResponse] = None):
        self._data = data
        self._response = response

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
