import os
import subprocess
from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse
from .exceptions import BranchDoesNotExist
from .exceptions import BranchExists
from .exceptions import ForkExists
from .exceptions import GiteaException
from .user import User


class Repo:
    @classmethod
    def get(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
    ) -> GiteaHTTPResponse:
        """
        Retrieve details about a repository.

        :param conn: Gitea ``Connection`` instance.
        :param owner: Owner of the repo.
        :param repo: Name of the repo.
        """
        url = conn.makeurl("repos", owner, repo)
        return conn.request("GET", url)

    @classmethod
    def clone(
        cls,
        conn: Connection,
        owner: str,
        repo: str,
        *,
        directory: Optional[str] = None,
        cwd: Optional[str] = None,
        anonymous: bool = False,
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
        :param anonymous: Whether to use``clone_url`` for an anonymous access or use authenticated ``ssh_url``.
        :param add_remotes: Determine and add 'parent' or 'fork' remotes to the cloned repo.
        """
        import shlex

        cwd = os.path.abspath(cwd) if cwd else os.getcwd()
        directory = directory if directory else repo
        # it's perfectly fine to use os.path.join() here because git can take an absolute path
        directory_abspath = os.path.join(cwd, directory)

        repo_data = cls.get(conn, owner, repo).json()
        clone_url = repo_data["clone_url"] if anonymous else repo_data["ssh_url"]

        remotes = {}
        if add_remotes:
            user = User.get(conn).json()
            if repo_data["owner"]["login"] == user["login"]:
                # we're cloning our own repo, setting remote to the parent (if exists)
                parent = repo_data["parent"]
                remotes["parent"] = parent["clone_url"] if anonymous else parent["ssh_url"]
            else:
                # we're cloning someone else's repo, setting remote to our fork (if exists)
                from . import Fork
                forks = Fork.list(conn, owner, repo).json()
                forks = [i for i in forks if i["owner"]["login"] == user["login"]]
                if forks:
                    assert len(forks) == 1
                    fork = forks[0]
                    remotes["fork"] = fork["clone_url"] if anonymous else fork["ssh_url"]

        env = os.environ.copy()
        ssh_args = []
        if ssh_private_key_path:
            ssh_args += [f"-i {shlex.quote(ssh_private_key_path)}"]
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

        subprocess.run(cmd, cwd=cwd, env=env, check=True)

        # setup remotes
        for name, url in remotes.items():
            cmd = ["git", "-C", directory_abspath, "remote", "add", name, url]
            subprocess.run(cmd, cwd=cwd, check=True)

        return directory_abspath
