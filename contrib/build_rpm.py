#!/usr/bin/python3


import argparse
import glob
import os
import re
from subprocess import check_output, run


PACKAGE_PRERELEASE_RE = re.compile(r"(?<=[\.\d])(?P<prerelease>a|alpha|b|beta|c|rc|pre|preview)(?P<num>\d*)$")
SPEC_VERSION_RE = re.compile(r"^(?P<version_tag>Version:[ \t]*).*", re.M)


class Git:
    def __init__(self, workdir=None):
        self.workdir = workdir
        self._topdir = None

    @property
    def topdir(self):
        if not self._topdir:
            cmd = ["git", "rev-parse", "--show-toplevel"]
            self._topdir = check_output(cmd, cwd=self.workdir, encoding="utf-8").strip()
        return self._topdir

    def describe(self):
        cmd = ["git", "describe", "--tags", "--abbrev=0"]
        git_tag = check_output(cmd, cwd=self.workdir, encoding="utf-8").strip()

        cmd = ["git", "describe", "--tags"]
        desc = check_output(cmd, cwd=self.workdir, encoding="utf-8").strip()

        if desc == git_tag:
            # we're at the latest git tag
            git_commits = 0
            git_hash = None
        else:
            # there are additional commits on top of the latest tag
            _, git_commits, git_hash = desc.rsplit("-", 2)
            git_commits = int(git_commits)
            git_hash = git_hash[1:]

        return git_tag, git_commits, git_hash

    def get_package_version(self):
        """
        Return package version based on a git tag.
        Pre-releases will be prefixed with '~' to comply with RPM pre-release versioning.
        """
        git_tag, git_commits, git_hash = self.describe()
        version = PACKAGE_PRERELEASE_RE.sub(r"~\g<prerelease>\g<num>", git_tag)
        if git_commits:
            version += f".{git_commits}.g{git_hash}"
        return version

    def archive(self, pkg_name, destdir=None):
        pkg_version = self.get_package_version()
        prefix = f"{pkg_name}-{pkg_version}"
        destdir = destdir or self.topdir
        tar_path = os.path.abspath(os.path.join(destdir, f"{prefix}.tar.gz"))
        cmd = ["git", "archive", "--format=tar.gz", f"--prefix={prefix}/", "HEAD", f"--output={tar_path}"]
        run(cmd, check=True, cwd=self.topdir)
        return tar_path


class Spec:
    @classmethod
    def find(cls, topdir):
        paths = ["", "contrib"]
        for path in paths:
            spec_paths = glob.glob(os.path.join(topdir, path, "*.spec"))
            if spec_paths:
                return cls(spec_paths[0])
        raise RuntimeError(f"Couldn't find spec under {topdir}")

    def __init__(self, path):
        self.path = os.path.abspath(path)
        self.topdir = os.path.dirname(self.path)
        self._name = None

    @property
    def name(self):
        if not self._name:
            cmd = ["rpmspec", self.path, "-q", "--qf=%{name}"]
            self._name = check_output(cmd, encoding="utf-8").strip()
        return self._name

    def set_version(self, version):
        with open(self.path, "r+", encoding="utf-8") as f:
            data = f.read()
            new_data = SPEC_VERSION_RE.sub(fr"\g<version_tag>{version}", data)
            f.seek(0)
            f.write(new_data)
            f.truncate()

    def build(self, srpm=True, rpm=True, nodeps=False):
        cmd = [
            "rpmbuild",
            self.path,
            "--define", f"_sourcedir {self.topdir}",
            "--define", f"_srcrpmdir {self.topdir}",
        ]
        if srpm and rpm:
            cmd.append("-ba")
        elif srpm:
            cmd.append("-bs")
        elif rpm:
            cmd.append("-bb")
        if nodeps:
            cmd.append("--nodeps")

        env = os.environ.copy()
        env["LC_ALL"] = "C.UTF-8"
        env["LANGUAGE"] = "C"
        run(cmd, check=True, encoding="utf-8", cwd=self.topdir, env=env)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rpm",
        action="store_true",
        help="Build binary RPMs",
    )
    parser.add_argument(
        "--srpm",
        action="store_true",
        help="Build source RPM",
    )
    parser.add_argument(
        "--nodeps",
        action="store_true",
        help="Do not verify build dependencies",
    )
    args = parser.parse_args()

    if not args.rpm and not args.srpm:
        parser.error('No build output specified. Please specify --rpm, --srpm or both.')

    git = Git()
    spec = Spec.find(git.topdir)
    git.archive(spec.name, destdir=spec.topdir)
    spec.set_version(git.get_package_version())
    spec.build(srpm=args.srpm, rpm=args.rpm, nodeps=args.nodeps)


if __name__ == "__main__":
    main()
