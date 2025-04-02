import os
import re
import subprocess
from typing import Optional
from typing import Tuple

from .connection import Connection
from .connection import GiteaHTTPResponse
from .user import User


class Repo:
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
        branch: Optional[str] = None,
        quiet: bool = False,
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
                if parent:
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

        ssh_args = []
        env = os.environ.copy()

        if ssh_private_key_path:
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
            cmd = ["git", "-C", directory_abspath, "config", "core.sshCommand", f"echo 'Using core.sshCommand: {env['GIT_SSH_COMMAND']}' >&2; {env['GIT_SSH_COMMAND']}"]
            subprocess.run(cmd, cwd=cwd, check=True)

        return directory_abspath
