"""
This module contains all common responses that osc will regularly parse.
"""

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING


from osc._private.xml import XmlParser, XmlSchemaType

if TYPE_CHECKING:
    from lxml import etree


@dataclass
class Status:
    """
    Represents https://build.opensuse.org/schema/status.xsd
    """
    summary = ""
    details = ""
    data: List[etree.Element] = field(default_factory=list)

    @staticmethod
    def from_xml_node(xml_node: etree.Element) -> "Status":
        """
        Accepts a given etree Element and converts it to a Status instance.

        :param xml_node: The XML node that should be used. Must be already validated.
        :return: The Status instance.
        """
        result = Status()
        result.summary = xml_node.get("summary")
        result.details = xml_node.get("details")
        result.data = list(xml_node.findall("summary//data"))
        return result


def parse_status(status_xml: str) -> Status:
    """
    Parses a given XML str according to the schema and returns the built object.

    :parma status_xml: The XML as a str.
    :raises ValueError: In case the XML validation failed.
    :return: The prepared Status instance.
    """
    schema_url = "https://build.opensuse.org/schema/status.xsd"
    parser = XmlParser(status_xml)
    parser.retrieve_validator(XmlSchemaType.XMLSCHEMA, schema_url)
    root = parser.validated_xml
    if root is None:
        raise ValueError("Invalid status XML passed!")
    return Status.from_xml_node(root)
