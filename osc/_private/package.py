import functools

from .. import oscerr
from . import api


@functools.total_ordering
class PackageBase:
    def __init__(self, apiurl, project, package):
        self.apiurl = apiurl
        self.project = project
        self.name = package

        self.rev = None
        self.vrev = None
        self.srcmd5 = None

        self.linkinfo = None
        self.files = []
        directory_node = self._get_directory_node()
        self._load_from_directory_node(directory_node)
        self._meta_node = None

    def __str__(self):
        return f"{self.project}/{self.name}"

    def __repr__(self):
        return super().__repr__() + f"({self})"

    def __hash__(self):
        return hash((self.name, self.project, self.apiurl))

    def __eq__(self, other):
        return (self.name, self.project, self.apiurl) == (other.name, other.project, other.apiurl)

    def __lt__(self, other):
        return (self.name, self.project, self.apiurl) < (other.name, other.project, other.apiurl)

    def _get_directory_node(self):
        raise NotImplementedError

    def _load_from_directory_node(self, directory_node):
        from .. import core as osc_core

        # attributes
        self.rev = directory_node.get("rev")
        self.vrev = directory_node.get("vrev")
        self.srcmd5 = directory_node.get("srcmd5")

        # files
        file_nodes = api.find_nodes(directory_node, "directory", "entry")
        for file_node in file_nodes:
            self.files.append(osc_core.File.from_xml_node(file_node))

        # linkinfo
        linkinfo_node = api.find_node(directory_node, "directory", "linkinfo")
        if linkinfo_node is not None:
            self.linkinfo = osc_core.Linkinfo()
            self.linkinfo.read(linkinfo_node)
            if self.linkinfo.project and not self.linkinfo.package:
                # if the link points to a package with the same name,
                # the name is omitted and we want it present for overall sanity
                self.linkinfo.package = self.name

    def _get_meta_node(self):
        raise NotImplementedError()

    def get_meta_value(self, option):
        if not self._meta_node:
            self._meta_node = self._get_meta_node()
        if not self._meta_node:
            return None
        node = api.find_node(self._meta_node, "package", option)
        if node is None or not node.text:
            raise oscerr.APIError(f"Couldn't get '{option}' from package _meta")
        return node.text


class ApiPackage(PackageBase):
    def __init__(self, apiurl, project, package, rev=None):
        # for loading the directory node from the API
        # the actual revision is loaded from the directory node
        self.__rev = rev
        super().__init__(apiurl, project, package)

    def _get_directory_node(self):
        url_path = ["source", self.project, self.name]
        url_query = {}
        if self.__rev:
            url_query["rev"] = self.__rev
        return api.get(self.apiurl, url_path, url_query)

    def _get_meta_node(self):
        url_path = ["source", self.project, self.name, "_meta"]
        url_query = {}
        return api.get(self.apiurl, url_path, url_query)


class LocalPackage(PackageBase):
    def __init__(self, path):
        from .. import store as osc_store

        self.dir = path
        self.store = osc_store.Store(self.dir)
        super().__init__(self.store.apiurl, self.store.project, self.store.package)

    def _get_directory_node(self):
        return self.store.read_xml_node("_files", "directory").getroot()

    def _get_meta_node(self):
        return self.store._meta_node
