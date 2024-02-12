"""
Functions that manipulate with XML.
"""


import xml.sax.saxutils
from xml.etree import ElementTree as ET


def xml_escape(string):
    """
    Escape the string so it's safe to use in XML and xpath.
    """
    entities = {
        '"': "&quot;",
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
        "&quot;": '"',
        "&apos;": "'",
    }
    if isinstance(string, bytes):
        return xml.sax.saxutils.unescape(string.decode("utf-8"), entities=entities).encode("utf-8")
    return xml.sax.saxutils.unescape(string, entities=entities)


def xml_strip_text(node):
    """
    Recursively strip inner text in nodes:
    - if text contains only whitespaces
    - if node contains child nodes
    """
    if node.text and not node.text.strip():
        node.text = None
    elif len(node) != 0:
        node.text = None
    for child in node:
        xml_strip_text(child)


def xml_indent_compat(elem, level=0):
    """
    XML indentation code for python < 3.9.
    Source: http://effbot.org/zone/element-lib.htm#prettyprint
    """
    i = "\n" + level * "  "
    if isinstance(elem, ET.ElementTree):
        elem = elem.getroot()
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = i + "  "
        for e in elem:
            xml_indent_compat(e, level + 1)
            if not e.tail or not e.tail.strip():
                e.tail = i + "  "
        if not e.tail or not e.tail.strip():
            e.tail = i
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = i


def xml_indent(root):
    """
    Indent XML so it looks pretty after printing or saving to file.
    """
    if hasattr(ET, "indent"):
        # ElementTree supports indent() in Python 3.9 and newer
        xml_strip_text(root)
        ET.indent(root)
    else:
        xml_indent_compat(root)
