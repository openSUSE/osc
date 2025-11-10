import os
import re
import subprocess
import urllib
from typing import Dict
from typing import Iterator
from typing import List
from typing import Optional
from typing import Tuple

from . import exceptions


class SshParseResult(urllib.parse.ParseResult):
    """
    Class to distinguish parsed SSH URLs
    """


class Git:
    @staticmethod
    def urlparse(url: str) -> urllib.parse.ParseResult:
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
            result = SshParseResult(scheme, netloc, path, params, query, fragment)
            return result

        result = urllib.parse.urlparse(url)
        if not result.netloc:
            # empty netloc is most likely an error, prepend and then discard scheme to trick urlparse()
            result = urllib.parse.urlparse("https://" + url)
            result = urllib.parse.ParseResult("", *list(result)[1:])
        return result

    @staticmethod
    def urljoin(url: str, path: str) -> str:
        """
        Append ``path`` to ``url``.
        """
        parts = Git.urlparse(url)
        # we're using os.path.normpath() and os.path.join() for working with URL paths, which may not be ideal, but seems to be working fine (on Linux)
        # we need to remove leading forward slash from ``parts.path`` because ``os.path.normpath("/../")`` resolves to "/" and we don't want that
        new_path = os.path.normpath(os.path.join(parts.path.lstrip("/"), path.lstrip("/")))

        parts = parts._replace(path=new_path)

        if isinstance(parts, SshParseResult):
            new_url = f"{parts.netloc}:{parts.path}"
        else:
            new_url = urllib.parse.urlunparse(parts)

        if new_path.startswith("../") or "/../" in new_path:
            raise ValueError(f"URL must not contain relative path: {new_url}")

        return new_url

    def __init__(self, workdir):
        self.abspath = os.path.abspath(workdir)

    def _run_git(self, args: List[str], mute_stderr: bool = False) -> str:
        # HACK: having 2 nearly identical commands is stupid, but it muted a mypy error
        if mute_stderr:
            return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath, stderr=subprocess.DEVNULL).strip()
        return subprocess.check_output(["git"] + args, encoding="utf-8", cwd=self.abspath).strip()

    @property
    def topdir(self) -> Optional[str]:
        """
        A custom implementation to `git rev-parse --show-toplevel` to avoid executing git which is sometimes unnecessary expensive.
        """
        path = self.abspath
        while path:
            if os.path.exists(os.path.join(path, ".git")):
                break

            path, dirname = os.path.split(path)

            if (path, dirname) == ("/", ""):
                # no git repo found
                return None

        return path

    def init(self, *, initial_branch: Optional[str] = None, quiet: bool = True, mute_stderr: bool = False):
        cmd = ["init"]
        if initial_branch:
            cmd += ["-b", initial_branch]
        if quiet:
            cmd += ["-q"]
        self._run_git(cmd, mute_stderr=mute_stderr)

    def clone(self,
        url: str,
        *,
        directory: Optional[str] = None,
        reference: Optional[str] = None,
        reference_if_able: Optional[str] = None,
        quiet: bool = True
    ):
        cmd = ["clone", url]
        if directory:
            cmd += [directory]
        if reference:
            cmd += ["--reference", reference]
        if reference_if_able:
            cmd += ["--reference-if-able", reference_if_able]
        if quiet:
            cmd += ["-q"]
        self._run_git(cmd)

    # BRANCHES

    @property
    def current_branch(self) -> Optional[str]:
        try:
            return self._run_git(["branch", "--show-current"], mute_stderr=True)
        except subprocess.CalledProcessError:
            return None

    def branch(self, branch: str, set_upstream_to: Optional[str] = None):
        cmd = ["branch"]
        if set_upstream_to:
            cmd += ["--set-upstream-to", set_upstream_to]
        cmd += [branch]
        return self._run_git(cmd)

    def branch_contains_commit(self, commit: str, branch: Optional[str] = None, remote: Optional[str] = None) -> bool:
        if not branch:
            branch = self.current_branch

        if remote:
            try:
                self._run_git(["merge-base", "--is-ancestor", commit, f"{remote}/{branch}"], mute_stderr=True)
                return True
            except subprocess.CalledProcessError:
                return False

        try:
            stdout = self._run_git(["branch", branch, "--contains", commit, "--format", "%(objectname) %(objecttype) %(refname)"])
            return stdout.strip() == f"{commit} commit refs/heads/{branch}"
        except subprocess.CalledProcessError:
            return False

    def get_branch_head(self, branch: Optional[str] = None) -> str:
        if not branch:
            branch = self.current_branch

        try:
            return self._run_git(["rev-parse", f"refs/heads/{branch}"], mute_stderr=True)
        except subprocess.CalledProcessError:
            raise exceptions.GitObsRuntimeError(f"Unable to retrieve HEAD from branch '{branch}'. Does the branch exist?")

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

    def reset(self, commit: Optional[str] = None, *, hard: bool = False):
        cmd = ["reset"]
        if commit:
            cmd += [commit]
        if hard:
            cmd += ["--hard"]
        self._run_git(cmd)

    def switch(self, branch: str, *, orphan: bool = False, quiet: bool = False):
        cmd = ["switch"]
        if quiet:
            cmd += ["--quiet"]
        if orphan:
            cmd += ["--orphan"]
        cmd += [branch]
        self._run_git(cmd)

    def fetch_pull_request(
        self,
        pull_number: int,
        *,
        remote: Optional[str] = None,
        commit: Optional[str] = None,
        depth: Optional[int] = None,
        force: bool = False,
    ):
        """
        Fetch pull/$pull_number/head to pull/$pull_number branch
        """
        target_branch = f"pull/{pull_number}"

        # if the branch exists and the head matches the expected commit, skip running 'git fetch'
        if commit and self.branch_exists(target_branch) and self.get_branch_head(target_branch) == commit:
            return target_branch

        if not remote:
            remote = self.get_current_remote()

        cmd = ["fetch", remote, f"pull/{pull_number}/head:{target_branch}"]
        if depth:
            cmd += ["--depth", str(depth)]
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

    def get_remote_url(self, name: Optional[str] = None) -> Optional[str]:
        if not name:
            name = self.get_current_remote()
        if not name:
            return None
        return self._run_git(["remote", "get-url", name])

    def add_remote(self, name: str, url: str):
        self._run_git(["remote", "add", name, url])

    def get_current_remote(self, fallback_to_origin: bool = True) -> Optional[str]:
        result = None
        try:
            result = self._run_git(["rev-parse", "--abbrev-ref", "@{u}"], mute_stderr=True)
            if result:
                result = result.split("/")[0]
        except subprocess.CalledProcessError:
            pass

        # the tracking information isn't sometimes set
        # let's fall back to 'origin' if available
        if not result and fallback_to_origin:
            try:
                self._run_git(["remote", "get-url", "origin"], mute_stderr=True)
                result = "origin"
            except subprocess.CalledProcessError:
                pass

        return result

    def fetch(self, name: Optional[str] = None):
        if name:
            cmd = ["fetch", name]
        else:
            cmd = ["fetch", "--all"]
        self._run_git(cmd)

    def get_owner_repo(self, remote: Optional[str] = None) -> Tuple[str, str]:
        remote_url = self.get_remote_url(name=remote)
        if not remote_url:
            raise exceptions.GitObsRuntimeError("Couldn't determine owner and repo due to a missing remote")
        return self.get_owner_repo_from_url(remote_url)

    @staticmethod
    def get_owner_repo_from_url(url: str) -> Tuple[str, str]:
        if "@" in url:
            # ssh://gitea@example.com:owner/repo.git
            # ssh://gitea@example.com:22/owner/repo.git
            url = url.rsplit("@", 1)[-1]
        parsed_url = urllib.parse.urlparse(url)
        path = parsed_url.path
        if path.endswith(".git"):
            path = path[:-4]
        owner, repo = path.strip("/").split("/")[-2:]
        return owner, repo

    # LFS

    def lfs_ls_files(self, ref: str = "HEAD", suffixes: Optional[List[str]] = None) -> Dict[str, str]:
        # TODO: --size; returns human readable string; can we somehow get the exact value in bytes instead?
        out = self._run_git(["lfs", "ls-files", "--long", ref])
        regex = re.compile(r"^(?P<checksum>[0-9a-f]+) [\*\-] (?P<path>.*)$")
        result = {}
        for line in out.splitlines():
            match = regex.match(line)
            if not match:
                continue

            checksum = match.groupdict()["checksum"]
            path = match.groupdict()["path"]

            if suffixes:
                found = False
                for suffix in suffixes:
                    if path.endswith(suffix):
                        found = True
                        break
                if not found:
                    continue

            result[path] = checksum
        return result

    def lfs_cat_file(self, filename: str, ref: str = "HEAD"):
        """
        A generator function that returns chunks of bytes of the requested file.
        """
        with subprocess.Popen(["git", "cat-file", "--filters", f"{ref}:{filename}"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, cwd=self.abspath) as proc:
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

    def push(self, remote: Optional[str] = None, branch: Optional[str] = None, *, set_upstream: Optional[str] = None, force: bool = False):
        cmd = ["push"]
        if force:
            cmd += ["--force"]
        if set_upstream:
            cmd += ["--set-upstream"]
        if remote:
            cmd += [remote]
            if branch:
                cmd += [branch]
        self._run_git(cmd)

    def ls_files(self, ref: str = "HEAD", suffixes: Optional[List[str]] = None) -> Dict[str, str]:
        out = self._run_git(["ls-tree", "-r", "--format=%(objectname) %(path)", ref])
        regex = re.compile(r"^(?P<checksum>[0-9a-f]+) (?P<path>.*)$")
        result = {}
        for line in out.splitlines():
            match = regex.match(line)
            if not match:
                continue

            checksum = match.groupdict()["checksum"]
            path = match.groupdict()["path"]

            if suffixes:
                found = False
                for suffix in suffixes:
                    if path.endswith(suffix):
                        found = True
                        break
                if not found:
                    continue

            result[path] = checksum
        return result

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

    # SUBMODULES

    def get_submodules(self) -> dict:
        SUBMODULE_RE = re.compile(r"^submodule\.(?P<submodule>[^=]*)\.(?P<key>[^\.=]*)=(?P<value>.*)$")
        STATUS_RE = re.compile(r"^(?P<status>.)(?P<commit>[a-f0-9]+) (?P<submodule>[^ ]+).*$")

        result = {}

        try:
            lines = self._run_git(["config", "--blob", "HEAD:.gitmodules", "--list"], mute_stderr=True).splitlines()
        except subprocess.CalledProcessError:
            # .gitmodules file is missing
            return {}

        for line in lines:
            match = SUBMODULE_RE.match(line)
            if not match:
                continue
            submodule = match.groupdict()["submodule"]
            key = match.groupdict()["key"]
            value = match.groupdict()["value"]
            #if key == "url":
            #    assert value.startswith("../../")
            submodule_entry = result.setdefault(submodule, {})
            submodule_entry[key] = value

        lines = self._run_git(["submodule", "status"]).splitlines()

        for line in lines:
            match = STATUS_RE.match(line)
            if not match:
                continue
            submodule = match.groupdict()["submodule"]
            commit = match.groupdict()["commit"]
            status = match.groupdict()["status"]
            result[submodule]["commit"] = commit
            result[submodule]["status"] = status

        remote_url = self.get_remote_url()
        for submodule_entry in result.values():
            url = submodule_entry["url"]
            if not url.startswith("../../"):
                submodule_entry["clone_url"] = url
                continue
 
            clone_url = self.urljoin(remote_url, submodule_entry["url"])
            owner, repo = self.get_owner_repo_from_url(clone_url)
            submodule_entry["clone_url"] = clone_url
            submodule_entry["owner"] = owner
            submodule_entry["repo"] = repo

        return result
