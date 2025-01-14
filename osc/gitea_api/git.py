import os
import subprocess
import urllib
from typing import Tuple


class Git:
    def __init__(self, workdir):
        self.abspath = os.path.abspath(workdir)

    def _run_git(self, args) -> str:
        return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath).strip()

    @property
    def current_branch(self) -> str:
        return self._run_git(["branch", "--show-current"])

    def get_branch_head(self, branch: str) -> str:
        return self._run_git(["rev-parse", branch])

    def get_remote_url(self, name: str = "origin") -> str:
        return self._run_git(["remote", "get-url", name])

    def get_owner_repo(self, remote: str = "origin") -> Tuple[str, str]:
        remote_url = self.get_remote_url(name=remote)
        parsed_remote_url = urllib.parse.urlparse(remote_url)
        path = parsed_remote_url.path
        if path.endswith(".git"):
            path = path[:-4]
        owner, repo = path.strip("/").split("/")[:2]
        return owner, repo
