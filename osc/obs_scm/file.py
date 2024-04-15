from functools import total_ordering

from ..util.xml import ET


@total_ordering
class File:
    """represent a file, including its metadata"""

    def __init__(self, name, md5, size, mtime, skipped=False):
        self.name = name
        self.md5 = md5
        self.size = size
        self.mtime = mtime
        self.skipped = skipped

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if isinstance(other, str):
            return self.name == other
        self_data = (self.name, self.md5, self.size, self.mtime, self.skipped)
        other_data = (other.name, other.md5, other.size, other.mtime, other.skipped)
        return self_data == other_data

    def __lt__(self, other):
        self_data = (self.name, self.md5, self.size, self.mtime, self.skipped)
        other_data = (other.name, other.md5, other.size, other.mtime, other.skipped)
        return self_data < other_data

    @classmethod
    def from_xml_node(cls, node):
        assert node.tag == "entry"
        kwargs = {
            "name": node.get("name"),
            "md5": node.get("md5"),
            "size": int(node.get("size")),
            "mtime": int(node.get("mtime")),
            "skipped": "skipped" in node.attrib,
        }
        return cls(**kwargs)

    def to_xml_node(self, parent_node):
        attributes = {
            "name": self.name,
            "md5": self.md5,
            "size": str(int(self.size)),
            "mtime": str(int(self.mtime)),
        }
        if self.skipped:
            attributes["skipped"] = "true"
        new_node = ET.SubElement(parent_node, "entry", attributes)
        return new_node
