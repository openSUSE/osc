from . import api
from .api import ET
from .. import oscerr


class APIXMLBase:
    def __init__(self, xml_root):
        self.root = xml_root

    def to_bytes(self):
        ET.indent(self.root, space="  ", level=0)
        return ET.tostring(self.root, encoding="utf-8")

    def to_string(self):
        return self.to_bytes().decode("utf-8")


class ProjectMeta(APIXMLBase):
    @classmethod
    def from_api(cls, apiurl, project):
        url_path = ["source", project, "_meta"]
        root = api.get(apiurl, url_path)
        obj = cls(root)
        return obj

    def to_api(self, apiurl, project):
        url_path = ["source", project, "_meta"]
        api.put(apiurl, url_path, data=self.to_bytes())

    def repository_list(self):
        result = []
        repo_nodes = api.find_nodes(self.root, "project", "repository")
        for repo_node in repo_nodes:
            arch_nodes = api.find_nodes(repo_node, "repository", "arch")
            path_nodes = api.find_nodes(repo_node, "repository", "path")
            repo = {
                "name": repo_node.attrib["name"],
                "archs": [i.text.strip() for i in arch_nodes],
                "paths": [i.attrib.copy() for i in path_nodes],
            }
            result.append(repo)
        return result

    def repository_add(self, name, arches, paths):
        node = api.find_node(self.root, "project")

        existing = api.find_node(self.root, "project", "repository", {"name": name})
        if existing:
            raise oscerr.OscValueError(f"Repository '{name}' already exists in project meta")

        repo_node = ET.SubElement(node, "repository", attrib={"name": name})

        for path_data in paths:
            ET.SubElement(repo_node, "path", attrib={
                "project": path_data["project"],
                "repository": path_data["repository"],
            })

        for arch in arches:
            arch_node = ET.SubElement(repo_node, "arch")
            arch_node.text = arch

        api.group_child_nodes(repo_node)
        api.group_child_nodes(node)

    def repository_remove(self, name):
        repo_node = api.find_node(self.root, "project", "repository", {"name": name})
        if repo_node is None:
            return
        self.root.remove(repo_node)

    def publish_add_disable_repository(self, name: str):
        publish_node = api.find_node(self.root, "project", "publish")
        if publish_node is None:
            project_node = api.find_node(self.root, "project")
            publish_node = ET.SubElement(project_node, "publish")
        else:
            disable_node = api.find_node(publish_node, "publish", "disable", {"repository": name})
            if disable_node is not None:
                return

        ET.SubElement(publish_node, "disable", attrib={"repository": name})
        api.group_child_nodes(publish_node)

    def publish_remove_disable_repository(self, name: str):
        publish_node = api.find_node(self.root, "project", "publish")
        if publish_node is None:
            return

        disable_node = api.find_node(publish_node, "publish", "disable", {"repository": name})
        if disable_node is not None:
            publish_node.remove(disable_node)

        if len(publish_node) == 0:
            self.root.remove(publish_node)
