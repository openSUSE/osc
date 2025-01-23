import os
import subprocess
import urllib
from typing import Optional
from typing import Tuple


class Git:
    def __init__(self, workdir):
        self.abspath = os.path.abspath(workdir)

    def _run_git(self, args: list) -> str:
        return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath).strip()

    def init(self, *, quiet=True):
        cmd = ["init"]
        if quiet:
            cmd += ["-q"]
        self._run_git(cmd)

    # BRANCHES

    @property
    def current_branch(self) -> str:
        return self._run_git(["branch", "--show-current"])

    def get_branch_head(self, branch: str) -> str:
        return self._run_git(["rev-parse", branch])

    def switch(self, branch: str):
        self._run_git(["switch", branch])

    def fetch_pull_request(
        self,
        pull_number: int,
        *,
        remote: str = "origin",
        force: bool = False,
    ):
        """
        Fetch pull/$pull_number/head to pull/$pull_number branch
        """
        target_branch = f"pull/{pull_number}"
        cmd = ["fetch", remote, f"pull/{pull_number}/head:{target_branch}"]
        if force:
            cmd += [
                "--force",
                "--update-head-ok",
            ]
        self._run_git(cmd)
        return target_branch

    # CONFIG

    def set_config(self, key: str, value: str):
        self._run_git(["config", key, value])

    # REMOTES

    def get_remote_url(self, name: str = "origin") -> str:
        return self._run_git(["remote", "get-url", name])

    def add_remote(self, name: str, url: str):
        self._run_git(["remote", "add", name, url])

    def fetch(self, name: Optional[str] = None):
        if name:
            cmd = ["fetch", name]
        else:
            cmd = ["fetch", "--all"]
        self._run_git(cmd)

    def get_owner_repo(self, remote: str = "origin") -> Tuple[str, str]:
        remote_url = self.get_remote_url(name=remote)
        if "@" in remote_url:
            # ssh://gitea@example.com:owner/repo.git
            # ssh://gitea@example.com:22/owner/repo.git
            remote_url = remote_url.rsplit("@", 1)[-1]
        parsed_remote_url = urllib.parse.urlparse(remote_url)
        path = parsed_remote_url.path
        if path.endswith(".git"):
            path = path[:-4]
        owner, repo = path.strip("/").split("/")[-2:]
        return owner, repo
