import os
import re
import subprocess
import urllib
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple


class Git:
    @staticmethod
    def urlparse(url) -> urllib.parse.ParseResult:
        """
        Parse git url.

        Supported formats:
            - https://example.com/owner/repo.git
            - https://example.com:1234/owner/repo.git
            - example.com/owner/repo.git
            - user@example.com:owner/repo.git
            - user@example.com:1234:owner/repo.git"
        """
        # try ssh clone url first
        pattern = r"(?P<netloc>[^@:]+@[^@:]+(:[0-9]+)?):(?P<path>.+)"
        match = re.match(pattern, url)
        if match:
            scheme = ""
            netloc = match.groupdict()["netloc"]
            path = match.groupdict()["path"]
            params = ''
            query = ''
            fragment = ''
            result = urllib.parse.ParseResult(scheme, netloc, path, params, query, fragment)
            return result

        result = urllib.parse.urlparse(url)
        if not result.netloc:
            # empty netloc is most likely an error, prepend and then discard scheme to trick urlparse()
            result = urllib.parse.urlparse("https://" + url)
            result = urllib.parse.ParseResult("", *list(result)[1:])
        return result

    def __init__(self, workdir):
        self.abspath = os.path.abspath(workdir)

    def _run_git(self, args: List[str], mute_stderr: bool = False) -> str:
        # HACK: having 2 nearly identical commands is stupid, but it muted a mypy error
        if mute_stderr:
            return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath, stderr=subprocess.DEVNULL).strip()
        return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath).strip()

    def init(self, *, initial_branch: Optional[str] = None, quiet: bool = True, mute_stderr: bool = False):
        cmd = ["init"]
        if initial_branch:
            cmd += ["-b", initial_branch]
        if quiet:
            cmd += ["-q"]
        self._run_git(cmd, mute_stderr=mute_stderr)

    def clone(self, url, directory: Optional[str] = None, quiet: bool = True):
        cmd = ["clone", url]
        if directory:
            cmd += [directory]
        if quiet:
            cmd += ["-q"]
        self._run_git(cmd)

    # BRANCHES

    @property
    def current_branch(self) -> str:
        return self._run_git(["branch", "--show-current"])

    def get_branch_head(self, branch: str) -> str:
        return self._run_git(["rev-parse", f"refs/heads/{branch}"])

    def branch_exists(self, branch: str) -> bool:
        try:
            self._run_git(["rev-parse", f"refs/heads/{branch}", "--"], mute_stderr=True)
        except subprocess.CalledProcessError:
            return False
        return True

    def commit_count(self, branch: str) -> int:
        try:
            commits = self._run_git(["rev-list", "--count", f"refs/heads/{branch}", "--"], mute_stderr=True)
            return int(commits)
        except subprocess.CalledProcessError:
            return -1

    def switch(self, branch: str, orphan: bool = False):
        cmd = ["switch"]
        if orphan:
            cmd += ["--orphan"]
        cmd += [branch]
        self._run_git(cmd)

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

    # LFS

    def lfs_ls_files(self, ref: str = "HEAD") -> List[Tuple[str, str]]:
        # TODO: --size; returns human readable string; can we somehow get the exact value in bytes instead?
        out = self._run_git(["lfs", "ls-files", "--long", ref])
        regex = re.compile(r"^(?P<checksum>[0-9a-f]+) [\*\-] (?P<filename>.*)$")
        result = []
        for line in out.splitlines():
            match = regex.match(line)
            if not match:
                continue
            result.append((match.group(2), match.group(1)))
        return result

    def lfs_cat_file(self, filename: str, ref: str = "HEAD"):
        """
        A generator function that returns chunks of bytes of the requested file.
        """
        with subprocess.Popen(["git", "cat-file", "--filters", f"{ref}:{filename}"], stdout=subprocess.PIPE, cwd=self.abspath) as proc:
            assert proc.stdout is not None
            while True:
                # 1MiB chunks are probably a good balance between memory consumption and performance
                data = proc.stdout.read(1024**2)
                if not data:
                    break
                yield data

    # FILES

    def add(self, files: List[str]):
        self._run_git(["add", *files])

    def commit(self, msg, *, allow_empty: bool = False):
        cmd = ["commit", "-m", msg]
        if allow_empty:
            cmd += ["--allow-empty"]
        self._run_git(cmd)

    def diff(self, ref_old: str, ref_new: str, src_prefix: Optional[str] = None, dst_prefix: Optional[str] = None) -> Iterator[bytes]:
        cmd = ["git", "diff", ref_old, ref_new]

        if src_prefix:
            src_prefix = src_prefix.rstrip("/") + "/"
            cmd += [f"--src-prefix={src_prefix}"]

        if dst_prefix:
            dst_prefix = dst_prefix.rstrip("/") + "/"
            cmd += [f"--dst-prefix={dst_prefix}"]

        # 1MiB chunks are probably a good balance between memory consumption and performance
        chunk_size = 1024**2
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, cwd=self.abspath) as proc:
            assert proc.stdout is not None
            while True:
                # read a chunk of data, make sure it ends with a newline
                # so we don't have to deal with split utf-8 characters and incomplete escape sequences later
                chunk = proc.stdout.read(chunk_size)
                chunk += proc.stdout.readline()
                if not chunk:
                    break
                yield chunk

    def status(self, *, porcelain: bool = False, untracked_files: bool = False):
        cmd = ["status", "--renames"]
        if untracked_files:
            cmd += ["--untracked-files"]
        if porcelain:
            cmd += ["--porcelain"]
        return self._run_git(cmd)
