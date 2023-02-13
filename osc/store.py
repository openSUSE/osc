"""
Store class wraps access to files in the '.osc' directory.
It is meant to be used as an implementation detail of Project and Package classes
and shouldn't be used in any code outside osc.
"""


import os
from xml.etree import ElementTree as ET

from . import oscerr
from ._private import api


class Store:
    STORE_DIR = ".osc"
    STORE_VERSION = "1.0"

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

        self.is_project = self.exists("_project") and not self.exists("_package")
        self.is_package = self.exists("_project") and self.exists("_package")

        if check and not any([self.is_project, self.is_package]):
            msg = f"Directory '{self.path}' is not a working copy"
            raise oscerr.NoWorkingCopy(msg)

    def __contains__(self, fn):
        return self.exists(fn)

    def __iter__(self):
        path = os.path.join(self.abspath, self.STORE_DIR)
        yield from os.listdir(path)

    def assert_is_project(self):
        if not self.is_project:
            msg = f"Directory '{self.path}' is not a working copy of a project"
            raise oscerr.NoWorkingCopy(msg)

    def assert_is_package(self):
        if not self.is_package:
            msg = f"Directory '{self.path}' is not a working copy of a package"
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
        value = "".join((f"{line}\n" for line in value))
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
        self.write_file(fn, value + "\n", subdir=subdir)

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
        path = self.get_path(fn, subdir=subdir)
        try:
            tree = ET.parse(path)
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
        self.assert_is_package()
        if self.exists("_scm"):
            msg = "Package '{self.path}' is managed via SCM"
            raise oscerr.NoWorkingCopy(msg)
        if not self.exists("_files"):
            msg = "Package '{self.path}' doesn't contain _files metadata"
            raise oscerr.NoWorkingCopy(msg)
        result = []
        directory_node = self.read_xml_node("_files", "directory").getroot()
        from . import core as osc_core
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
        if items is not None and len(items) != 3:
            msg = f"Package '{self.path}' contains _last_buildroot metadata that doesn't contain 3 lines: [repo, arch, vm_type]"
            raise oscerr.NoWorkingCopy(msg)
        return items

    @last_buildroot.setter
    def last_buildroot(self, value):
        self.assert_is_package()
        if len(value) != 3:
            raise ValueError("A list with exactly 3 items is expected: [repo, arch, vm_type]")
        self.write_list("_last_buildroot", value)

    @property
    def _meta_node(self):
        if not self.exists("_meta"):
            return None
        if self.is_package:
            root = self.read_xml_node("_meta", "package").getroot()
        else:
            root = self.read_xml_node("_meta", "project").getroot()
        return root
