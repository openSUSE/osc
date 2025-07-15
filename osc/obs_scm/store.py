"""
Store class wraps access to files in the '.osc' directory.
It is meant to be used as an implementation detail of Project and Package classes
and shouldn't be used in any code outside osc.
"""


import os

from .. import oscerr
from .._private import api
from ..util.xml import ET

from typing import List

# __store_version__ is to be incremented when the format of the working copy
# "store" changes in an incompatible way. Please add any needed migration
# functionality to check_store_version().
__store_version__ = '2.0'


class Store:
    STORE_DIR = ".osc"
    STORE_VERSION = "2.0"

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

    def __init__(self, path, check=True):
        self.path = path
        self.abspath = os.path.abspath(self.path)

        if check:
            check_store_version(self.abspath)

        self.is_project = self.exists("_project") and not self.exists("_package")
        self.is_package = self.exists("_project") and self.exists("_package")

        if check and not any([self.is_project, self.is_package]):
            msg = f"Directory '{self.path}' is not an OBS SCM working copy"
            raise oscerr.NoWorkingCopy(msg)

    def __contains__(self, fn):
        return self.exists(fn)

    def __iter__(self):
        path = os.path.join(self.abspath, self.STORE_DIR)
        for fn in os.listdir(path):
            full_path = os.path.join(path, fn)
            if os.path.isdir(full_path):
                continue
            yield fn

    def assert_is_project(self):
        if not self.is_project:
            msg = f"Directory '{self.path}' is not an OBS SCM working copy of a project"
            raise oscerr.NoWorkingCopy(msg)

    def assert_is_package(self):
        if not self.is_package:
            msg = f"Directory '{self.path}' is not an OBS SCM working copy of a package"
            raise oscerr.NoWorkingCopy(msg)

    def get_path(self, fn, subdir=None):
        # sanitize input to ensure that joining path works as expected
        fn = fn.lstrip("/")
        if subdir:
            subdir = subdir.lstrip("/")
            return os.path.join(self.abspath, self.STORE_DIR, subdir, fn)
        return os.path.join(self.abspath, self.STORE_DIR, fn)

    def exists(self, fn, subdir=None):
        return os.path.exists(self.get_path(fn, subdir=subdir))

    def unlink(self, fn, subdir=None):
        try:
            os.unlink(self.get_path(fn, subdir=subdir))
        except FileNotFoundError:
            pass

    def read_file(self, fn, subdir=None):
        if not self.exists(fn, subdir=subdir):
            return None
        with open(self.get_path(fn, subdir=subdir), encoding="utf-8") as f:
            return f.read()

    def write_file(self, fn, value, subdir=None):
        if value is None:
            self.unlink(fn, subdir=subdir)
            return
        try:
            if subdir:
                os.makedirs(self.get_path(subdir))
            else:
                os.makedirs(self.get_path(""))
        except FileExistsError:
            pass

        old = self.get_path(fn, subdir=subdir)
        new = self.get_path(f"{fn}.new", subdir=subdir)
        try:
            with open(new, "w", encoding="utf-8") as f:
                f.write(value)
            os.rename(new, old)
        except:
            if os.path.exists(new):
                os.unlink(new)
            raise

    def read_list(self, fn, subdir=None):
        if not self.exists(fn, subdir=subdir):
            return None
        with open(self.get_path(fn, subdir=subdir), encoding="utf-8") as f:
            return [line.rstrip("\n") for line in f]

    def write_list(self, fn, value, subdir=None):
        if value is None:
            self.unlink(fn, subdir=subdir)
            return
        if not isinstance(value, (list, tuple)):
            msg = f"The argument `value` should be list, not {type(value).__name__}"
            raise TypeError(msg)
        value = "".join((f"{line or ''}\n" for line in value))
        self.write_file(fn, value, subdir=subdir)

    def read_string(self, fn, subdir=None):
        if not self.exists(fn, subdir=subdir):
            return None
        with open(self.get_path(fn, subdir=subdir), encoding="utf-8") as f:
            return f.readline().strip()

    def write_string(self, fn, value, subdir=None):
        if value is None:
            self.unlink(fn, subdir=subdir)
            return
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        if not isinstance(value, str):
            msg = f"The argument `value` should be str, not {type(value).__name__}"
            raise TypeError(msg)
        self.write_file(fn, f"{value}\n", subdir=subdir)

    def read_int(self, fn):
        if not self.exists(fn):
            return None
        result = self.read_string(fn)
        if not result.isdigit():
            return None
        return int(result)

    def write_int(self, fn, value, subdir=None):
        if value is None:
            self.unlink(fn, subdir=subdir)
            return
        if not isinstance(value, int):
            msg = f"The argument `value` should be int, not {type(value).__name__}"
            raise TypeError(msg)
        value = str(value)
        self.write_string(fn, value, subdir=subdir)

    def read_xml_node(self, fn, node_name, subdir=None):
        from ..util.xml import xml_parse

        path = self.get_path(fn, subdir=subdir)
        try:
            tree = xml_parse(path)
        except SyntaxError as e:
            msg = f"Unable to parse '{path}': {e}"
            raise oscerr.NoWorkingCopy(msg)
        root = tree.getroot()
        assert root.tag == node_name
        # TODO: return root?
        return tree

    def write_xml_node(self, fn, node_name, node, subdir=None):
        path = self.get_path(fn, subdir=subdir)
        assert node.tag == node_name
        api.write_xml_node_to_file(node, path)

    def _sanitize_apiurl(self, value):
        # apiurl shouldn't end with a slash, strip it so we can use apiurl without modifications
        # in config['api_host_options'][apiurl] and other places
        if isinstance(value, str):
            value = value.strip("/")
        elif isinstance(value, bytes):
            value = value.strip(b"/")
        return value

    @property
    def apiurl(self):
        return self._sanitize_apiurl(self.read_string("_apiurl"))

    @apiurl.setter
    def apiurl(self, value):
        self.write_string("_apiurl", self._sanitize_apiurl(value))

    @property
    def project(self):
        return self.read_string("_project")

    @project.setter
    def project(self, value):
        self.write_string("_project", value)

    @property
    def package(self):
        return self.read_string("_package")

    @package.setter
    def package(self, value):
        self.write_string("_package", value)

    @property
    def scmurl(self):
        return self.read_string("_scm")

    @scmurl.setter
    def scmurl(self, value):
        return self.write_string("_scm", value)

    @property
    def size_limit(self):
        return self.read_int("_size_limit")

    @size_limit.setter
    def size_limit(self, value):
        return self.write_int("_size_limit", value)

    @property
    def to_be_added(self):
        self.assert_is_package()
        return self.read_list("_to_be_added") or []

    @to_be_added.setter
    def to_be_added(self, value):
        self.assert_is_package()
        return self.write_list("_to_be_added", value)

    @property
    def to_be_deleted(self):
        self.assert_is_package()
        return self.read_list("_to_be_deleted") or []

    @to_be_deleted.setter
    def to_be_deleted(self, value):
        self.assert_is_package()
        return self.write_list("_to_be_deleted", value)

    @property
    def in_conflict(self):
        self.assert_is_package()
        return self.read_list("_in_conflict") or []

    @in_conflict.setter
    def in_conflict(self, value):
        self.assert_is_package()
        return self.write_list("_in_conflict", value)

    @property
    def osclib_version(self):
        return self.read_string("_osclib_version")

    @property
    def files(self):
        from .. import core as osc_core

        self.assert_is_package()
        if self.exists("_scm"):
            msg = "Package '{self.path}' is managed via SCM"
            raise oscerr.NoWorkingCopy(msg)
        if not self.exists("_files"):
            msg = "Package '{self.path}' doesn't contain _files metadata"
            raise oscerr.NoWorkingCopy(msg)
        result = []
        directory_node = self.read_xml_node("_files", "directory").getroot()
        for entry_node in api.find_nodes(directory_node, "directory", "entry"):
            result.append(osc_core.File.from_xml_node(entry_node))
        return result

    @files.setter
    def files(self, value):
        if not isinstance(value, (list, tuple)):
            msg = f"The argument `value` should be list, not {type(value).__name__}"
            raise TypeError(msg)

        root = ET.Element("directory")
        for file_obj in sorted(value):
            file_obj.to_xml_node(root)
        self.write_xml_node("_files", "directory", root)

    @property
    def last_buildroot(self):
        self.assert_is_package()
        items = self.read_list("_last_buildroot")
        if items is None:
            return items

        if len(items) != 3:
            msg = f"Package '{self.path}' contains _last_buildroot metadata that doesn't contain 3 lines: [repo, arch, vm_type]"
            raise oscerr.NoWorkingCopy(msg)

        if items[2] in ("", "None"):
            items[2] = None

        return items

    @last_buildroot.setter
    def last_buildroot(self, value):
        self.assert_is_package()
        if len(value) != 3:
            raise ValueError("A list with exactly 3 items is expected: [repo, arch, vm_type]")
        self.write_list("_last_buildroot", value)

    @property
    def build_repositories(self):
        from ..core import Repo

        self.assert_is_package()
        entries = self.read_list("_build_repositories")
        if entries is None:
            return None

        repos = []
        for entry in entries:
            name, arch = entry.split(" ")
            repos.append(Repo(name=name, arch=arch))

        return repos

    @build_repositories.setter
    def build_repositories(self, value):
        from ..core import Repo

        self.assert_is_package()
        entries = []
        for i in value:
            if not isinstance(i, Repo):
                raise ValueError(f"The value is not an instance of 'Repo': {i}")
            entries.append(f"{i.name} {i.arch}")
        self.write_list("_build_repositories", entries)

    @property
    def _meta_node(self):
        if not self.exists("_meta"):
            return None
        if self.is_package:
            root = self.read_xml_node("_meta", "package").getroot()
        else:
            root = self.read_xml_node("_meta", "project").getroot()
        return root

    def sources_get_path(self, file_name: str) -> str:
        if "/" in file_name:
            raise ValueError(f"Plain file name expected: {file_name}")
        result = os.path.join(self.abspath, self.STORE_DIR, "sources", file_name)
        os.makedirs(os.path.dirname(result), exist_ok=True)
        return result

    def sources_list_files(self) -> List[str]:
        result = []
        invalid = []

        topdir = os.path.join(self.abspath, self.STORE_DIR, "sources")

        if not os.path.isdir(topdir):
            return []

        for fn in os.listdir(topdir):
            if self.sources_is_file(fn):
                result.append(fn)
            else:
                invalid.append(fn)

        if invalid:
            msg = ".osc/sources contains entries other than regular files"
            raise oscerr.WorkingCopyInconsistent(self.project, self.package, invalid, msg)

        return result

    def sources_is_file(self, file_name: str) -> bool:
        return os.path.isfile(self.sources_get_path(file_name))

    def sources_delete_file(self, file_name: str):
        try:
            os.unlink(self.sources_get_path(file_name))
        except:
            pass


store = '.osc'


def check_store_version(dir):
    global store

    versionfile = os.path.join(dir, store, '_osclib_version')
    try:
        with open(versionfile) as f:
            v = f.read().strip()
    except:
        # we need to initialize store without `check` to avoid recursive calling of check_store_version()
        if Store(dir, check=False).is_project:
            v = '1.0'
        else:
            v = ''

    if v == '':
        msg = f'Error: "{os.path.abspath(dir)}" is not an osc working copy.'
        if os.path.exists(os.path.join(dir, '.svn')):
            msg = msg + '\nTry svn instead of osc.'
        raise oscerr.NoWorkingCopy(msg)

    if v != __store_version__:
        migrated = False

        if v in ['0.2', '0.3', '0.4', '0.5', '0.6', '0.7', '0.8', '0.9', '0.95', '0.96', '0.97', '0.98', '0.99']:
            # no migration needed, only change metadata version to 1.0
            s = Store(dir, check=False)
            v = "1.0"
            s.write_string("_osclib_version", v)
            migrated = True

        if v == "1.0":
            store_dir = os.path.join(dir, store)
            sources_dir = os.path.join(dir, store, "sources")
            sources_dir_mv = sources_dir

            if os.path.isfile(sources_dir):
                # there is a conflict with an existing "sources" file
                sources_dir_mv = os.path.join(dir, store, "_sources")

            os.makedirs(sources_dir_mv, exist_ok=True)

            s = Store(dir, check=False)
            if s.is_package and not s.scmurl:
                from .package import Package
                from .project import Project

                scm_files = [i.name for i in s.files]

                for fn in os.listdir(store_dir):
                    old_path = os.path.join(store_dir, fn)
                    new_path = os.path.join(sources_dir_mv, fn)
                    if not os.path.isfile(old_path):
                        continue
                    if fn in Package.REQ_STOREFILES or fn in Package.OPT_STOREFILES:
                        continue
                    if fn.startswith("_") and fn not in scm_files:
                        continue
                    if os.path.isfile(old_path):
                        os.rename(old_path, new_path)

            if sources_dir != sources_dir_mv:
                os.rename(sources_dir_mv, sources_dir)

            v = "2.0"
            s.write_string("_osclib_version", v)
            migrated = True

        if migrated:
            return

        msg = f'The osc metadata of your working copy "{dir}"'
        msg += f'\nhas __store_version__ = {v}, but it should be {__store_version__}'
        msg += '\nPlease do a fresh checkout or update your client. Sorry about the inconvenience.'
        raise oscerr.WorkingCopyWrongVersion(msg)


def is_project_dir(d):
    from ..store import get_store

    try:
        store = get_store(d)
        return store.is_project
    except oscerr.NoWorkingCopy:
        return False


def is_package_dir(d):
    from ..store import get_store

    try:
        store = get_store(d)
        return store.is_package
    except oscerr.NoWorkingCopy:
        return False


def read_filemeta(dir):
    from ..store import get_store

    store = get_store(dir)

    store.assert_is_package()
    if store.exists("_scm"):
        msg = "Package '{store.path}' is managed via SCM"
        raise oscerr.NoWorkingCopy(msg)
    if not store.exists("_files"):
        msg = "Package '{store.path}' doesn't contain _files metadata"
        raise oscerr.NoWorkingCopy(msg)

    return store.read_xml_node("_files", "directory")


def store_readlist(dir, name):
    from ..store import get_store

    store = get_store(dir)
    return store.read_list(name)


def read_tobeadded(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.to_be_added


def read_tobedeleted(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.to_be_deleted


def read_sizelimit(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.size_limit


def read_inconflict(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.in_conflict


def store_read_project(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.project


def store_read_package(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.package


def store_read_scmurl(dir):
    import warnings
    from ..store import get_store

    warnings.warn(
        "osc.core.store_read_scmurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    store = get_store(dir)
    return store.scmurl


def store_read_apiurl(dir, defaulturl=True):
    import warnings
    from ..store import get_store

    warnings.warn(
        "osc.core.store_read_apiurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    store = get_store(dir)
    return store.apiurl


def store_read_last_buildroot(dir):
    from ..store import get_store

    store = get_store(dir)
    return store.last_buildroot


def store_write_string(dir, file, string, subdir=None):
    from ..store import get_store

    store = get_store(dir)
    store.write_string(file, string, subdir)


def store_write_project(dir, project):
    from ..store import get_store

    store = get_store(dir)
    store.project = project


def store_write_apiurl(dir, apiurl):
    import warnings
    from ..store import get_store

    warnings.warn(
        "osc.core.store_write_apiurl() is deprecated. "
        "You should be using high-level classes such as Store, Project or Package instead.",
        DeprecationWarning
    )
    store = get_store(dir)
    store.apiurl = apiurl


def store_write_last_buildroot(dir, repo, arch, vm_type):
    from ..store import get_store

    store = get_store(dir)
    store.last_buildroot = repo, arch, vm_type


def store_unlink_file(dir, file):
    from ..store import get_store

    store = get_store(dir)
    store.unlink(file)


def store_read_file(dir, file):
    from ..store import get_store

    store = get_store(dir)
    return store.read_file(file)


def store_write_initial_packages(dir, project, subelements):
    from ..store import get_store

    store = get_store(dir)

    root = ET.Element('project', name=project)
    root.extend(subelements)

    store.write_xml_node("_packages", "project", root)


def delete_storedir(store_dir):
    """
    This method deletes a store dir.
    """
    from ..core import delete_dir

    head, tail = os.path.split(store_dir)
    if tail == '.osc':
        delete_dir(store_dir)
