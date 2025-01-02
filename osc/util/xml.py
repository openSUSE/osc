"""
Functions that manipulate with XML.
"""

import io
import xml.sax.saxutils
from typing import Union
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


def _extend_parser_error_msg(e: ET.ParseError, text: Union[str, bytes]):
    from ..output import tty

    y, x = e.position
    text = text.splitlines()[y-1][x-1:]

    if isinstance(text, bytes):
        text = text.decode("utf-8")

    new_text = ""
    for char in text:
        if char >= " ":
            new_text += char
            continue
        byte = ord(char)
        char = f"0x{byte:0>2X}"
        char = tty.colorize(char, "bg_red")
        new_text += char
    e.msg += ": " + new_text


def xml_fromstring(text: str):
    """
    xml.etree.ElementTree.fromstring() wrapper that extends error message in ParseError
    exceptions with a snippet of the broken XML.
    """
    try:
        return ET.fromstring(text)
    except ET.ParseError as e:
        _extend_parser_error_msg(e, text)
        raise


def xml_parse(source):
    """
    xml.etree.ElementTree.parse() wrapper that extends error message in ParseError
    exceptions with a snippet of the broken XML.
    """
    if isinstance(source, str):
        # source is a file name
        with open(source, "rb") as f:
            data = f.read()
    else:
        # source is an IO object
        data = source.read()

    if isinstance(data, bytes):
        f = io.BytesIO(data)
    else:
        f = io.StringIO(data)

    try:
        return ET.parse(f)
    except ET.ParseError as e:
        _extend_parser_error_msg(e, data)
        raise
