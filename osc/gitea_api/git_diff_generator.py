"""
Changing a submodule commit in a git repo requires cloning the submodule and changing it's HEAD.
This is relatively slow, especially when working with many submodules.
You can create 2 instances of ``GitDiffGenerator`` and set their files and submodules and produce a diff,
that can be applied and used for submiting a pull request.
This is primarily made for making submodule changes while grouping project pull requests during staging.

Limitations:
- works with text files only
- renames are not supported
"""


import configparser
from typing import List
from typing import Optional


class GitmodulesEntry:
    def __init__(self, gitmodules_parser: "GitmodulesParser", path: str):
        self._parser = gitmodules_parser
        self._path = path
        assert self.path == path

    @property
    def section(self) -> str:
        return f'submodule "{self._path}"'

    def _get_value(self, name: str) -> str:
        return self._parser.get(self.section, name, raw=True, fallback=None)

    def _set_value(self, name: str, value: Optional[str]):
        if value is None:
            self._parser.remove_option(self.section, name)
        else:
            self._parser.set(self.section, name, value)

    @property
    def path(self) -> str:
        return self._get_value("path")

    @property
    def url(self) -> str:
        return self._get_value("url")

    @url.setter
    def url(self, value: str):
        return self._set_value("url", value)

    @property
    def branch(self) -> str:
        return self._get_value("branch")

    @branch.setter
    def branch(self, value: str):
        return self._set_value("branch", value)


class GitmodulesParser(configparser.ConfigParser):
    def _write_section(self, fp, section_name, section_items, delimiter, *args, **kwargs):
        import io

        # prefix keys with spaces to be compatible with standard .gitmodules format created by git
        section_items = [(f"\t{k}", v) for k, v in section_items]

        buffer = io.StringIO()
        super()._write_section(
            fp=buffer,
            section_name=section_name,
            section_items=section_items,
            delimiter=delimiter,
            *args,
            **kwargs,
        )

        # remove the trailing newline
        gitmodules_str = buffer.getvalue()
        if gitmodules_str[-1] == "\n":
            gitmodules_str = gitmodules_str[:-1]

        fp.write(gitmodules_str)

    def to_string(self) -> str:
        import io

        buffer = io.StringIO()
        self.write(buffer)
        return buffer.getvalue()


class GitDiffGenerator:
    def __init__(self, gitmodules_str: str = None):
        self._files = {}
        self._submodule_commits = {}
        self._gitmodules = GitmodulesParser()
        if gitmodules_str:
            self._gitmodules.read_string(gitmodules_str)

    def _check_path(self, path: str):
        if path.startswith("/"):
            raise ValueError(f"A path in a git repo must not be absolute: {path}")

    def set_file(self, path: str, contents: Optional[str]):
        self._check_path(path)
        if contents is None:
            self._files.pop(path, None)
        else:
            self._files[path] = contents

    def _get_file_lines(self, path) -> Optional[List[str]]:
        self._check_path(path)
        if not path in self._files:
            return None
        return self._files[path].splitlines()

    def set_submodule_commit(self, path: str, commit: Optional[str]):
        self._check_path(path)
        if commit is None:
            if self.has_gitmodules_entry(path):
                raise ValueError(f"Need to delete a corresponding .gitmodules entry first: {path}")
            self._submodule_commits.pop(path, None)
        else:
            if not self.has_gitmodules_entry(path):
                raise ValueError(f"Path has no corresponding .gitmodules entry: {path}")
            self._submodule_commits[path] = commit

    def _get_submodule_lines(self, path) -> Optional[List[str]]:
        self._check_path(path)
        if not path in self._submodule_commits:
            return None
        commit = self._submodule_commits[path]
        return [f"Subproject commit {commit}"]

    def _get_gitmodules_section_name(self, path: str) -> str:
        return f'submodule "{path}"'

    def has_gitmodules_entry(self, path: str) -> bool:
        return self._gitmodules.has_section(self._get_gitmodules_section_name(path))

    def get_gitmodules_entry(self, path) -> Optional[GitmodulesEntry]:
        if not self.has_gitmodules_entry(path):
            return None
        return GitmodulesEntry(self._gitmodules, path)

    def create_gitmodules_entry(self, *, path: str, url: str, branch: str):
        try:
            section_name = self._get_gitmodules_section_name(path)
            self._gitmodules.add_section(section_name)
            self._gitmodules.set(section_name, "path", path)
            self._gitmodules.set(section_name, "url", url)
            self._gitmodules.set(section_name, "branch", branch)
        except configparser.DuplicateSectionError:
            raise ValueError(f"A .gitmodules entry '{path}' already exists.")
        return self.get_gitmodules_entry(path)

    def update_gitmodules_entry(self, *, path: str, url: str, branch: str):
        try:
            result = self.create_gitmodules_entry(path=path, url=url, branch=branch)
        except ValueError:
            result = self.get_gitmodules_entry(path)
            result.url = url
            result.branch = branch
        return result

    def delete_gitmodules_entry(self, path: str):
        self._gitmodules.remove_section(self._get_gitmodules_section_name(path))

    def diff(self, other: "GitDiffGenerator"):
        """
        How the current state
        """
        import difflib

        # generate .gitmodules diff
        self_gitmodules = self._gitmodules.to_string()
        other_gitmodules = other._gitmodules.to_string()
        if self_gitmodules or other_gitmodules:
            path = ".gitmodules"
            old_lines = self_gitmodules.splitlines()
            new_lines = other_gitmodules.splitlines()
            yield from difflib.unified_diff(
                old_lines or [],
                new_lines or [],
                fromfile=f"a/{path}" if old_lines is not None else "/dev/null",
                tofile=f"b/{path}" if new_lines is not None else "/dev/null",
                lineterm="",
            )

        # generate submodules diff
        all_submodules = sorted(
            set(self._submodule_commits) | set(other._submodule_commits)
        )
        for path in all_submodules:
            old_lines = self._get_submodule_lines(path)
            new_lines = other._get_submodule_lines(path)
            yield from difflib.unified_diff(
                old_lines or [],
                new_lines or [],
                fromfile=f"a/{path}" if old_lines is not None else "/dev/null",
                tofile=f"b/{path}" if new_lines is not None else "/dev/null",
                lineterm="",
            )

        # generate files diff
        all_files = sorted(set(self._files) | set(other._files))
        for path in all_files:
            old_lines = self._get_file_lines(path)
            new_lines = other._get_file_lines(path)
            yield from difflib.unified_diff(
                old_lines or [],
                new_lines or [],
                fromfile=f"a/{path}" if old_lines is not None else "/dev/null",
                tofile=f"b/{path}" if new_lines is not None else "/dev/null",
                lineterm="",
            )

        yield "\n"
