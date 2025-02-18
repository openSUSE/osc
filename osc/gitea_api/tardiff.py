import os
import shutil
import subprocess
from typing import Iterator

from . import git


GIT_EMPTY_COMMIT = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"


class TarDiff:
    def __init__(self, path):
        self.git = git.Git(path)
        os.makedirs(self.path, exist_ok=True)
        self.git.init(initial_branch="empty", quiet=True, mute_stderr=True)
        # the git repo is switched to this branch by default to hide the files from disk
        self.git.commit("empty branch", allow_empty=True)

    @property
    def path(self):
        return self.git.abspath

    def _get_branch_name(self, filename: str, checksum: str) -> str:
        filename = os.path.basename(filename)
        return f"{filename}-{checksum}"

    def add_archive(self, filename: str, checksum: str, data: Iterator[bytes]) -> str:
        """
        Create a branch with expanded archive.
        The easiest way of obtaining the `checksum` is via running `git lfs ls-files --long`.
        """

        # make sure we don't use the path anywhere
        filename = os.path.basename(filename)

        branch = self._get_branch_name(filename, checksum)

        # detect if a branch exists and is not empty; do nothing if it's the case
        if self.git.branch_exists(branch) and self.git.commit_count(branch) > 0:
            return branch

        # create an empty branch
        self.git.switch(branch, orphan=True)
        # TODO: mute stdout

        # remove any existing contents but ".git" directory
        for fn in os.listdir(self.path):
            if fn == ".git":
                continue
            shutil.rmtree(os.path.join(self.path, fn))

        # extract archive
        # We use bsdtar, because tar cannot determine compression from stdin automatically.
        # Stripping the first path component works fine for regular source archives with %{name}/%{version}/ prefix
        # but it may need an improvement for other archives.
        proc = subprocess.Popen(
            ["bsdtar", "xf", "-", "--strip-components=1"],
            stdin=subprocess.PIPE,
            cwd=self.path,
        )
        assert proc.stdin is not None
        for chunk in data:
            proc.stdin.write(chunk)
        proc.communicate()
        assert proc.returncode == 0

        # add files and commit
        self.git.add(["--all"])
        self.git.commit(msg=f"import {filename} with checksum {checksum}")

        self.git.switch("empty")

        # TODO: git gc?

        return branch

    def diff_archives(self, src_filename, src_checksum, dst_filename, dst_checksum) -> Iterator[bytes]:
        if src_filename:
            src_filename = os.path.basename(src_filename)
            src_branch = self._get_branch_name(src_filename, src_checksum)
            src_branch = f"refs/heads/{src_branch}"
        else:
            src_filename = "/dev/null"
            src_branch = GIT_EMPTY_COMMIT

        if dst_filename:
            dst_filename = os.path.basename(dst_filename)
            dst_branch = self._get_branch_name(dst_filename, dst_checksum)
            dst_branch = f"refs/heads/{dst_branch}"
        else:
            dst_filename = "/dev/null"
            dst_branch = GIT_EMPTY_COMMIT

        yield from self.git.diff(src_branch, dst_branch, src_prefix=src_filename, dst_prefix=dst_filename)
