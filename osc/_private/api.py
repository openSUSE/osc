"""
Functions that communicate with OBS API
and work with related XML data.
"""


import xml.sax.saxutils
from xml.etree import ElementTree as ET


def get(apiurl, path, query=None):
    """
    Send a GET request to OBS.

    :param apiurl: OBS apiurl.
    :type  apiurl: str
    :param path: URL path segments.
    :type  path: list(str)
    :param query: URL query values.
    :type  query: dict(str, str)
    :returns: Parsed XML root.
    :rtype:   xml.etree.ElementTree.Element
    """
    from .. import connection as osc_connection
    from .. import core as osc_core

    assert apiurl
    assert path

    if not isinstance(path, (list, tuple)):
        raise TypeError("Argument `path` expects a list of strings")

    url = osc_core.makeurl(apiurl, path, query)
    with osc_connection.http_GET(url) as f:
        root = ET.parse(f).getroot()
    return root


def post(apiurl, path, query=None):
    """
    Send a POST request to OBS.

    :param apiurl: OBS apiurl.
    :type  apiurl: str
    :param path: URL path segments.
    :type  path: list(str)
    :param query: URL query values.
    :type  query: dict(str, str)
    :returns: Parsed XML root.
    :rtype:   xml.etree.ElementTree.Element
    """
    from .. import connection as osc_connection
    from .. import core as osc_core

    assert apiurl
    assert path

    if not isinstance(path, (list, tuple)):
        raise TypeError("Argument `path` expects a list of strings")

    url = osc_core.makeurl(apiurl, path, query)
    with osc_connection.http_POST(url) as f:
        root = ET.parse(f).getroot()
    return root


def find_nodes(root, root_name, node_name):
    """
    Find nodes with given `node_name`.
    Also, verify that the root tag matches the `root_name`.

    :param root: Root node.
    :type  root: xml.etree.ElementTree.Element
    :param root_name: Expected (tag) name of the root node.
    :type  root_name: str
    :param node_name: Name of the nodes we're looking for.
    :type  node_name: str
    :returns: List of nodes that match the given `node_name`.
    :rtype:   list(xml.etree.ElementTree.Element)
    """
    assert root.tag == root_name
    return root.findall(node_name)


def find_node(root, root_name, node_name=None):
    """
    Find a single node with given `node_name`.
    If `node_name` is not specified, the root node is returned.
    Also, verify that the root tag matches the `root_name`.

    :param root: Root node.
    :type  root: xml.etree.ElementTree.Element
    :param root_name: Expected (tag) name of the root node.
    :type  root_name: str
    :param node_name: Name of the nodes we're looking for.
    :type  node_name: str
    :returns: The node that matches the given `node_name`
              or the root node if `node_name` is not specified.
    :rtype:   xml.etree.ElementTree.Element
    """

    assert root.tag == root_name
    if node_name:
        return root.find(node_name)
    return root


def write_xml_node_to_file(node, path, indent=True):
    """
    Write a XML node to a file.

    :param node: Node to write.
    :type  node: xml.etree.ElementTree.Element
    :param path: Path to a file that will be written to.
    :type  path: str
    :param indent: Whether to indent (pretty-print) the written XML.
    :type  indent: bool
    """
    if indent:
        xml_indent(node)
    ET.ElementTree(node).write(path)


def xml_escape(string):
    """
    Escape the string so it's safe to use in XML and xpath.
    """
    entities = {
        "\"": "&quot;",
        "'": "&apos;",
    }
    if isinstance(string, bytes):
        return xml.sax.saxutils.escape(string.decode("utf-8"), entities=entities).encode("utf-8")
    return xml.sax.saxutils.escape(string, entities=entities)


def xml_indent(root):
    """
    Indent XML so it looks pretty after printing or saving to file.
    """
    if hasattr(ET, "indent"):
        # ElementTree supports indent() in Python 3.9 and newer
        ET.indent(root)
    else:
        from .. import core as osc_core
        osc_core.xmlindent(root)
