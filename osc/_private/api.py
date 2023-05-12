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


def put(apiurl, path, query=None, data=None):
    """
    Send a PUT request to OBS.

    :param apiurl: OBS apiurl.
    :type  apiurl: str
    :param path: URL path segments.
    :type  path: list(str)
    :param query: URL query values.
    :type  query: dict(str, str)
    :returns: Parsed XML root.
    :rtype:   xml.etree.ElementTree.Element
    """
    from osc import connection as osc_connection
    from osc import core as osc_core

    assert apiurl
    assert path

    if not isinstance(path, (list, tuple)):
        raise TypeError("Argument `path` expects a list of strings")

    url = osc_core.makeurl(apiurl, path, query)
    with osc_connection.http_PUT(url, data=data) as f:
        root = osc_core.ET.parse(f).getroot()
    return root


def _to_xpath(*args):
    """
    Convert strings and dictionaries to xpath:
        string gets translated to a node name
        dictionary gets translated to [@key='value'] predicate

    All values are properly escaped.

    Examples:
        args: ["directory", "entry", {"name": "osc"}]
        result: "directory/entry[@name='osc']"

        args: ["attributes", "attribute", {"namespace": "OBS", "name": "BranchSkipRepositories"}, "value"]
        result: "attributes/attribute[@namespace='OBS'][@name='BranchSkipRepositories']/value"
    """
    xpath = ""
    for arg in args:
        if isinstance(arg, str):
            arg = xml.sax.saxutils.escape(arg)
            xpath += f"/{arg}"
        elif isinstance(arg, dict):
            for key, value in arg.items():
                key = xml.sax.saxutils.escape(key)
                value = xml.sax.saxutils.escape(value)
                xpath += f"[@{key}='{value}']"
        else:
            raise TypeError(f"Argument '{arg}' has invalid type '{type(arg).__name__}'. Expected types: str, dict")

    # strip the leading slash because we're making a relative search
    xpath = xpath.lstrip("/")
    return xpath


def find_nodes(root, root_name, *args):
    """
    Find nodes with given `node_name`.
    Also, verify that the root tag matches the `root_name`.

    :param root: Root node.
    :type  root: xml.etree.ElementTree.Element
    :param root_name: Expected (tag) name of the root node.
    :type  root_name: str
    :param *args: Simplified xpath notation: strings are node names, dictionaries translate to [@key='value'] predicates.
    :type  *args: list[str, dict]
    :returns: List of nodes that match xpath based on the given `args`.
    :rtype:   list(xml.etree.ElementTree.Element)
    """
    assert root.tag == root_name
    return root.findall(_to_xpath(*args))


def find_node(root, root_name, *args):
    """
    Find a single node with given `node_name`.
    If `node_name` is not specified, the root node is returned.
    Also, verify that the root tag matches the `root_name`.

    :param root: Root node.
    :type  root: xml.etree.ElementTree.Element
    :param root_name: Expected (tag) name of the root node.
    :type  root_name: str
    :param *args: Simplified xpath notation: strings are node names, dictionaries translate to [@key='value'] predicates.
    :type  *args: list[str, dict]
    :returns: The node that matches xpath based on the given `args`
              or the root node if `args` are not specified.
    :rtype:   xml.etree.ElementTree.Element
    """

    assert root.tag == root_name
    if not args:
        # only verify the root tag
        return root
    return root.find(_to_xpath(*args))


def group_child_nodes(node):
    nodes = node[:]
    result = []

    while nodes:
        # look at the tag of the first node
        tag = nodes[0].tag

        # collect all nodes with the same tag and append them to the result
        # then repeat the step for the next tag(s)
        matches = []
        others = []
        for i in nodes:
            if i.tag == tag:
                matches.append(i)
            else:
                others.append(i)

        result += matches
        nodes = others

    node[:] = result


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


def xml_unescape(string):
    """
    Decode XML entities in the string.
    """
    entities = {
        "&quot;": "\"",
        "&apos;": "'",
    }
    if isinstance(string, bytes):
        return xml.sax.saxutils.unescape(string.decode("utf-8"), entities=entities).encode("utf-8")
    return xml.sax.saxutils.unescape(string, entities=entities)


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
