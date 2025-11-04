import fcntl
import fnmatch
import json
import os
import sys
import typing
import urllib.parse
from pathlib import Path
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Union

from .. import oscerr
from ..util.models import BaseModel
from ..util.models import Field


if typing.TYPE_CHECKING:
    from ..core import Repo
    from ..obs_api import GiteaConnection


class Header(BaseModel):
    type: str = Field()
    version: str = Field()


class Meta(BaseModel):
    """
    Metadata about a project or a package managed in git that is stored in .git/obs/<branch>/meta.json
    """

    header: Header = Field(default={"type": "obs-metadata-store", "version": "1"})
    apiurl: Optional[str] = Field()
    project: Optional[str] = Field()
    package: Optional[str] = Field()

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Lock:
    def __init__(self, path: str):
        self.path = os.path.abspath(path)
        self.handle = None

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.handle = open(self.path, "w")
        fcntl.flock(self.handle, fcntl.LOCK_EX)

    def __exit__(self, type, value, traceback):
        if self.handle:
            fcntl.flock(self.handle, fcntl.LOCK_UN)
            self.handle.close()
            try:
                os.remove(self.path)
            except OSError:
                pass


class BuildRoot(BaseModel):
    """
    Model that encapsulates last_buildroot values, providing better API than the original tuple.

    For compatibility, assigning values to repo, arch, vm_type variables is also supported via __iter__()
    and __eq__ is capable of comparing with a tuple with (repo, arch, vm_type).
    """
    repo: str = Field()
    arch: str = Field()
    vm_type: Optional[str] = Field()

    def __iter__(self):
        for field in self.__fields__:
            yield getattr(self, field)

    def __eq__(self, other):
        if isinstance(other, tuple) and len(other) == 3:
            return (self.repo, self.arch, self.vm_type) == other
        return super().__eq__(other)


class LocalGitStore:
    """
    A class for managing OBS metadata in .git.
    It is not supposed to be used directly, it's a base class for GitStore that adds logic for resolving the values from multiple places.
    """

    _BRANCH_MISMATCH_WARNING_PRINTED = set()

    @classmethod
    def is_project_dir(cls, path):
        try:
            store = cls(path)
        except oscerr.NoWorkingCopy:
            return False
        return store.is_project

    @classmethod
    def is_package_dir(cls, path):
        try:
            store = cls(path)
        except oscerr.NoWorkingCopy:
            return False
        return store.is_package

    def __init__(self, path: str, *, check: bool = True):
        from ..gitea_api import Git
        from ..obs_scm import Store
        from .manifest import Manifest
        from .manifest import Subdirs

        self._git = Git(path)
        self._check = check

        if not os.path.isdir(self.abspath) or not self._git.topdir:
            msg = f"Directory '{path}' is not a Git SCM working copy"
            raise oscerr.NoWorkingCopy(msg)

        if not self._git.current_branch:
            # branch is required for determining and storing metadata
            msg = (
                f"Directory '{path}' contains a git repo that has no branch or is in a detached HEAD state.\n"
                "If it is a Git SCM working copy, switch to a branch to continue."
            )
            raise oscerr.NoWorkingCopy(msg)

        # 'package' is the default type that applies to all git repos that are not projects (we have no means of detecting packages)
        self._type = "package"
        self._topdir = self._git.topdir

        self.manifest = None

        # we detect projects by looking for certain file names next to .git
        files = ["_manifest", "_config", "_pbuild", "_subdirs"]
        for fn in files:
            path = os.path.join(self._git.topdir, fn)
            if os.path.exists(path):
                self._type = "project"
                break

        if self.type == "project":
            manifest_path = os.path.join(self._git.topdir, "_manifest")
            subdirs_path = os.path.join(self._git.topdir, "_subdirs")

            if os.path.exists(manifest_path):
                self.manifest = Manifest.from_file(manifest_path)
            elif os.path.exists(subdirs_path):
                self.manifest = Subdirs.from_file(subdirs_path)
            else:
                # empty manifest considers all top-level directories as packages
                self.manifest = Manifest({})

            if self._git.topdir != self.abspath:
                package_topdir = self.manifest.resolve_package_path(project_path=self._git.topdir, package_path=self.abspath)
                if package_topdir:
                    self._type = "package"
                    self._topdir = package_topdir
                    self.manifest = None

        self.project_store = None
        if self.type == "package":
            # load either .osc or .git project store from the directory above topdir
            if not self.project_store:
                try:
                    store = Store(os.path.join(self.topdir, ".."))
                    store.assert_is_project()
                    self.project_store = store
                except oscerr.NoWorkingCopy:
                    pass

            if not self.project_store:
                try:
                    # turn off 'check' because we want at least partial metadata to be inherited to the package
                    store = GitStore(os.path.join(self.topdir, ".."), check=False)
                    if store.type == "project":
                        self.project_store = store
                except oscerr.NoWorkingCopy:
                    pass

        elif self.type == "project":
            # load .osc project store that is next to .git and may provide medatata we don't have
            try:
                store = Store(self.topdir)
                store.assert_is_project()
                self.project_store = store
            except oscerr.NoWorkingCopy:
                pass

    @property
    def abspath(self) -> str:
        return self._git.abspath

    @property
    def topdir(self) -> str:
        return self._topdir

    def reset(self, *, branch: Optional[str] = None):
        self._delete_meta(branch=branch)

    def _get_path(self, path: List[str], *, branch: Optional[str] = None):
        assert isinstance(path, list)
        # sanitization for os.path.join()
        branch = branch if branch is not None else self._git.current_branch
        branch = branch.strip("/")
        branch = branch.replace("/", "__")
        path = [i.strip("/") for i in path]

        result = self._git._run_git(["rev-parse", "--path-format=absolute", "--git-path", "obs"])
        result = os.path.join(result, branch, *path)
        return result

    def _lock(self):
        return Lock(self._get_path([".lock"]))

    def _delete_meta(self, *, branch: Optional[str] = None):
        path = self._get_path(["meta.json"], branch=branch)
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass

    def _read_meta(self, *, branch: Optional[str] = None) -> Meta:
        path = self._get_path(["meta.json"], branch=branch)
        try:
            with self._lock():
                return Meta.from_file(path)
        except FileNotFoundError:
            return Meta()

    def _write_meta(self, *, branch: Optional[str] = None, **kwargs):
        path = self._get_path(["meta.json"], branch=branch)
        with self._lock():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                meta = Meta.from_file(path)
            except FileNotFoundError:
                meta = Meta()
            meta.update(**kwargs)
            meta.to_file(path)

    @property
    def type(self):
        return self._type

    @property
    def is_project(self) -> bool:
        return self.type == "project"

    @property
    def is_package(self) -> bool:
        return self.type == "package"

    def assert_is_project(self):
        if not self.is_project:
            msg = f"Directory '{self.abspath}' is not a Git SCM working copy of a project"
            raise oscerr.NoWorkingCopy(msg)

        missing = []
        for name in ["apiurl", "project"]:
            if not getattr(self, name):
                missing.append(name)

        if missing:
            msg = f"Git SCM project working copy doesn't have the following metadata set: {', '.join(missing)}\n"

            if "apiurl" in missing:
                msg += (
                    "\n"
                    "To fix apiurl:\n"
                    " - Run 'git-obs meta pull' to retrieve the 'obs_apiurl' value from 'obs/configuration' repo, 'main' branch, 'configuration.yaml' file\n"
                    " - Run 'git-obs meta set --apiurl=...\n"
                )

            if "project" in missing:
                msg += (
                    "\n"
                    "To fix project:\n"
                    " - Set 'obs_project' in '_manifest' file\n"
                    " - Run 'git-obs meta set --project=...\n"
                )

            msg += "\nCheck git-obs-metadata man page for more details"

            raise oscerr.NoWorkingCopy(msg)

    def assert_is_package(self):
        if not self.is_package:
            msg = f"Directory '{self.abspath}' is not a Git SCM working copy of a package"
            raise oscerr.NoWorkingCopy(msg)

        if self.project_store and hasattr(self.project_store, "_git") and self.project_store._git.current_branch != self._git.current_branch:
            key = (self.project_store._git.current_branch, self._git.current_branch)
            if key not in self.__class__._BRANCH_MISMATCH_WARNING_PRINTED:
                from osc.output import tty

                # print the warning only once and store the information in the class
                self.__class__._BRANCH_MISMATCH_WARNING_PRINTED.add(key)
                msg = (
                    f"{tty.colorize('WARNING', 'yellow,bold')}: "
                    "Git SCM package working copy is switched to a different branch than it's corresponding parent project\n"
                    f" - Package branch: {self._git.current_branch}\n"
                    f" - Project branch: {self.project_store._git.current_branch}\n"
                    f" - Package path: {self.topdir}\n"
                    f" - Project path: {self.project_store.topdir}"
                )
                print(msg, file=sys.stderr)

        missing = []
        for name in ["apiurl", "project", "package"]:
            if not getattr(self, name):
                missing.append(name)

        if missing:
            msg = f"Git SCM package working copy doesn't have the following metadata set: {', '.join(missing)}\n"

            if self.project_store:
                msg += f" - The package has a parent project checkout: {self.project_store.abspath}\n"
            else:
                msg += " - The package has no parent project checkout\n"

            if "apiurl" in missing:
                msg += "\n"
                msg += "To fix apiurl:\n"
                if self.project_store:
                    msg += (
                        " - Run 'git-obs meta pull' IN THE PROJECT in the parent directory to retrieve the 'obs_apiurl' value from 'obs/configuration' repo, 'main' branch, 'configuration.yaml' file\n"
                        " - run 'git-obs meta set --apiurl=...' IN THE PROJECT\n"
                    )
                else:
                    msg += (
                        " - Run 'git-obs meta set --apiurl=...'\n"
                    )

            if "project" in missing:
                msg += "\n"
                msg += "To fix project:\n"

                if self.project_store:
                    msg += (
                        " - Set 'obs_project' in '_manifest' file IN THE PROJECT\n"
                        " - Run 'git-obs meta set --project=...' IN THE PROJECT\n"
                    )
                else:
                    msg += (
                        f" - Set 'obs_project' in the matching _ObsPrj git repo, '{self._git.current_branch}' branch, '_manifest' file\n"
                        "   Run 'git-obs meta pull'\n"
                        " - Run 'git-obs meta set --project=...'\n"
                    )

            msg += "\nCheck git-obs-metadata man page for more details"

            raise oscerr.NoWorkingCopy(msg)

    # APIURL

    @property
    def apiurl(self) -> Optional[str]:
        return self.get_apiurl()

    @apiurl.setter
    def apiurl(self, value: Optional[str]):
        self.set_apiurl(value)

    def get_apiurl(self, *, branch: Optional[str] = None) -> Optional[str]:
        return self._read_meta(branch=branch).apiurl

    def set_apiurl(self, value: Optional[str], *, branch: Optional[str] = None):
        self._write_meta(apiurl=value, branch=branch)

    # PROJECT

    @property
    def project(self) -> Optional[str]:
        return self.get_project()

    @project.setter
    def project(self, value: Optional[str]):
        self.set_project(value)

    def get_project(self, *, branch: Optional[str] = None) -> Optional[str]:
        return self._read_meta(branch=branch).project

    def set_project(self, value: Optional[str], *, branch: Optional[str] = None):
        self._write_meta(project=value, branch=branch)

    # PACKAGE

    @property
    def package(self) -> Optional[str]:
        return self.get_package()

    @package.setter
    def package(self, value: Optional[str]):
        self.set_package(value)

    def get_package(self, *, branch: Optional[str] = None) -> Optional[str]:
        return self._read_meta(branch=branch).package

    def set_package(self, value: Optional[str], *, branch: Optional[str] = None):
        if self._check:
            self.assert_is_package()
        self._write_meta(package=value, branch=branch)

    # CACHE
    # buildinfo and buildconfig files are considered a cache, they can be safely deleted at any time

    def cache_list_files(self, *, pattern: Optional[str] = None, branch: Optional[str] = None):
        path = self._get_path(["cache"], branch=branch)
        files = os.listdir(path)
        if pattern:
            files = [i for i in files if fnmatch.fnmatch(i, pattern)]
        return files

    def cache_get_path(self, filename: str, *, branch: Optional[str] = None, makedirs: bool = False) -> str:
        if "/" in filename:
            raise ValueError(f"Filename must not contain path: {filename}")
        branch = branch or self._git.current_branch
        path = self._get_path(["cache", filename], branch=branch)
        if makedirs:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    def cache_read_file(self, filename: str, *, branch: Optional[str] = None) -> Optional[bytes]:
        path = self.cache_get_path(filename, branch=branch)
        with self._lock():
            try:
                with open(path, "rb") as f:
                    return f.read()
            except FileNotFoundError:
                return None

    def cache_write_file(self, filename: str, data: bytes, *, branch: Optional[str] = None):
        path = self.cache_get_path(filename, branch=branch)
        with self._lock():
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)

    def cache_delete_files(self, filenames: List[str], *, branch: Optional[str] = None):
        branch = branch or self._git.current_branch
        with self._lock():
            for filename in filenames:
                path = self.cache_get_path(filename, branch=branch)
                try:
                    os.unlink(path)
                except FileNotFoundError:
                    pass

    # LAST BUILDROOT

    _LAST_BUILDROOT_FILE = "last-buildroot.json"
    _LAST_BUILDROOT_VALUE_TYPE = Union[Optional[Tuple[str, str, Optional[str]]], BuildRoot]

    @property
    def last_buildroot(self) -> _LAST_BUILDROOT_VALUE_TYPE:
        return self.get_last_buildroot()

    @last_buildroot.setter
    def last_buildroot(self, value: _LAST_BUILDROOT_VALUE_TYPE):
        self.set_last_buildroot(value)

    def get_last_buildroot(self, *, branch: Optional[str] = None) -> _LAST_BUILDROOT_VALUE_TYPE:
        result = self.cache_read_file(self._LAST_BUILDROOT_FILE, branch=branch)
        if result is None:
            return None
        obj = BuildRoot.from_string(result.decode("utf-8"))
        return obj

    def set_last_buildroot(self, value: _LAST_BUILDROOT_VALUE_TYPE, *, branch: Optional[str] = None):
        if value is None:
            self.cache_delete_files([self._LAST_BUILDROOT_FILE])
            return

        if isinstance(value, tuple):
            if len(value) != 3:
                raise ValueError("A tuple with exactly 3 items is expected: (repo, arch, vm_type)")
            obj = BuildRoot(repo=value[0], arch=value[1], vm_type=value[2])
        else:
            obj = value

        data = json.dumps(obj.dict()).encode("utf-8")
        self.cache_write_file(self._LAST_BUILDROOT_FILE, data, branch=branch)

    # BUILD REPOSITORIES

    _BUILD_REPOSITORIES_FILE = "build-repositories.json"
    _BUILD_REPOSITORIES_VALUE_TYPE = Optional[List["Repo"]]

    @property
    def build_repositories(self) -> _BUILD_REPOSITORIES_VALUE_TYPE:
        return self.get_build_repositories()

    @build_repositories.setter
    def build_repositories(self, value: Optional[List["Repo"]]):
        return self.set_build_repositories(value)

    def get_build_repositories(self, *, branch: Optional[str] = None) -> Optional[List["Repo"]]:
        from ..core import Repo

        result = self.cache_read_file(self._BUILD_REPOSITORIES_FILE, branch=branch)
        if result is None:
            return None
        result = json.loads(result)
        return [Repo(**i) for i in result]

    def set_build_repositories(self, value: Optional[List["Repo"]], *, branch: Optional[str] = None):
        from ..core import Repo

        if value is None:
            self.cache_delete_files([self._BUILD_REPOSITORIES_FILE])
            return

        repos = []
        if value is not None:
            for i in value:
                if not isinstance(i, Repo):
                    raise ValueError(f"The value is not an instance of 'Repo': {i}")
                repos.append(i.dict())
        self.cache_write_file(self._BUILD_REPOSITORIES_FILE, json.dumps(repos).encode("utf-8"), branch=branch)


class GitStore(LocalGitStore):
    """
    A class for managing OBS metadata in .git that also reads the values from additional locations
    such as the parent project's metadata or the _manifest file.
    """
    def __init__(self, path: str, check: bool = True, *, cached: bool = True):
        super().__init__(path, check=check)
        self.cached = cached
        self._cache = {}

        if self._check:
            if self.is_project:
                self.assert_is_project()
            else:
                self.assert_is_package()

    def _resolve_meta(self, field_name: str, *, allow_none: bool = False):
        result = None

        # values cached in the object
        if self.cached:
            result = self._cache.get(field_name, None)

        # local git store
        if result is None:
            result = getattr(super(), field_name)

        # _manifest file in the project
        if result is None and self.is_project and self.manifest:
            result = getattr(self.manifest, f"obs_{field_name}", None) or None

        # project.build file in the project
        if result is None and self.is_project and field_name == "project":
            path = os.path.join(self.topdir, "project.build")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    result = f.read().strip() or None

        # package = directory name; package must be part of a project checkout
        if result is None and self.is_package and self.project_store is not None and field_name == "package":
            result = os.path.basename(self.topdir)

        # package = repo name from the current remote url
        if result is None and self.is_package and field_name == "package":
            remote_url = self._git.get_remote_url()
            if remote_url:
                result = Path(urllib.parse.urlsplit(remote_url).path).stem

        # project: get value from .osc which is next to .git
        # package: get value from the parent project's store
        if result is None and self.project_store:
            result = getattr(self.project_store, field_name, None)

        if self.cached:
            self._cache[field_name] = result

        return result

    @property
    def apiurl(self) -> Optional[str]:
        return self._resolve_meta("apiurl")

    @property
    def project(self) -> Optional[str]:
        return self._resolve_meta("project")

    @property
    def package(self) -> Optional[str]:
        return self._resolve_meta("package")

    @property
    def scmurl(self) -> Optional[str]:
        return self._git.get_remote_url()

    def pull(self, gitea_conn) -> Dict[str, Optional[str]]:
        from osc.git_scm.configuration import Configuration
        from osc.git_scm.manifest import Manifest
        from .. import gitea_api

        apiurl = None
        project = None

        # read apiurl and project from _manifest that lives in <owner>/_ObsPrj, matching <branch>
        # XXX: when the target branch doesn't exist, file from the default branch is returned
        if self.is_package:
            owner, _ = self._git.get_owner_repo()
            repo = "_ObsPrj"
            branch = self._git.current_branch

            try:
                url = gitea_conn.makeurl("repos", owner, repo, "raw", "_manifest", query={"ref": branch})
                response = gitea_conn.request("GET", url)
                if response.data:
                    manifest = Manifest.from_string(response.data.decode("utf-8"))
                    if manifest.obs_apiurl:
                        apiurl = manifest.obs_apiurl
                    if manifest.obs_project:
                        project = manifest.obs_project
            except gitea_api.GiteaException as e:
                if e.status != 404:
                    raise

            if not project:
                try:
                    url = gitea_conn.makeurl("repos", owner, repo, "raw", "project.build", query={"ref": branch})
                    response = gitea_conn.request("GET", url)
                    if response.data:
                        value = response.data.decode("utf-8").strip()
                        if value:
                            project = value
                except gitea_api.GiteaException as e:
                    if e.status != 404:
                        raise

        # read apiurl from the global configuration in obs/configuration, 'main' branch, 'configuration.yaml' file
        if not apiurl:
            try:
                url = gitea_conn.makeurl("repos", "obs", "configuration", "raw", "configuration.yaml", query={"ref": "main"})
                response = gitea_conn.request("GET", url)
                if response.data:
                    configuration = Configuration.from_string(response.data.decode("utf-8"))
                    if configuration.obs_apiurl:
                        apiurl = configuration.obs_apiurl
            except gitea_api.GiteaException as e:
                if e.status != 404:
                    raise

        if apiurl:
            self.set_apiurl(apiurl)

        if project:
            self.set_project(project)

        # return the values we've set
        result = {
            "apiurl": apiurl,
            "project": project,
        }
        return result
