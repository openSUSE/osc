"""
This module is a wrapper around lxml that encapsulates XML related functionality in a manner that it consolidates common
tasks that are performed inside osc.
"""

import enum
from typing import Optional

from lxml import etree, isoschematron

from osc import core


class XmlSchemaType(enum.Enum):
    """
    This enum represents all available XML schema types that osc can handle with the help of this module.
    """
    DTD = 1
    RELAXNG = 2
    XMLSCHEMA = 3
    SCHEMATRON = 4


def retrieve_xml_document(xml_url: str, http_method=core.http_GET) -> str:
    """
    Downloads a textfile and returns it as a str.

    :param xml_url: The URL that is used to download the document.
    :param http_method: Defines the HTTP method that is being used to download the file.
    :return: The downloaded file or an empty str.
    """
    xml_schema = ""
    for data in core.streamfile(xml_url, http_method):
        xml_schema += core.decode_it(data)
    return xml_schema


class XmlParser:
    """
    An instance of this class may be used to parse a single XML string that may optionally be validated with a given
    XML schema.
    """
    def __init__(self, xml_str: str):
        self.raw_xml = xml_str
        self.parsed_xml = etree.fromstring(self.raw_xml)
        self.schema_validator = None
        self.__http_method = core.http_GET

    def retrieve_dtd(self, schema_url: str) -> etree.DTD:
        """
        Retrieves the schema from the network and converts it to a validator object ready for use.

        :param schema_url: The URL to retrieve the schema.
        :return: The DTD object that has the schema included.
        """
        xml_schema = retrieve_xml_document(schema_url, self.__http_method)
        return etree.DTD(xml_schema)

    def retrieve_xmlschema(self, schema_url: str) -> etree.XMLSchema:
        """
        Retrieves the schema from the network and converts it to a validator object ready for use.

        :param schema_url: The URL to retrieve the schema.
        :return: The XML Schema object that has the schema included.
        """
        xml_schema = retrieve_xml_document(schema_url, self.__http_method)
        return etree.XMLSchema(etree.parse(xml_schema))

    def retrieve_relexng_schema(self, schema_url: str) -> etree.RelaxNG:
        """
        Retrieves the schema from the network and converts it to a validator object ready for use.

        :param schema_url: The URL to retrieve the schema.
        :return: The Relax NG object that has the schema included.
        """
        xml_schema = retrieve_xml_document(schema_url, self.__http_method)
        return etree.RelaxNG(xml_schema)

    def retrieve_schematron(self, schema_url: str) -> isoschematron.Schematron:
        """
        Retrieves the schema from the network and converts it to a validator object ready for use.

        :param schema_url: The URL to retrieve the schema.
        :return: The Schematron object that has the schema included.
        """
        xml_schema = retrieve_xml_document(schema_url, self.__http_method)
        return isoschematron.Schematron(etree.parse(xml_schema))

    def retrieve_validator(self, schema_type: XmlSchemaType, schema_url: str, http_method=None):
        """
        This method retrieves the schema that was given to it and prepares the XML validator instance from lxml for it.

        :param schema_type: The schema type that has to be used to parse it.
        :param schema_url: The URL to retrieve the schema.
        :param http_method: The HTTP method to retrieve the schema. If the default value (None) is used, then
                            http_GET is utilized.
        """
        if http_method is not None:
            self.__http_method = http_method
        if schema_type == XmlSchemaType.DTD:
            self.schema_validator = self.retrieve_dtd(schema_url)
        elif schema_type == XmlSchemaType.RELAXNG:
            self.schema_validator = self.retrieve_relexng_schema(schema_url)
        elif schema_type == XmlSchemaType.XMLSCHEMA:
            self.schema_validator = self.retrieve_xmlschema(schema_url)
        elif schema_type == XmlSchemaType.SCHEMATRON:
            self.schema_validator = self.retrieve_schematron(schema_url)
        else:
            raise ValueError("Unknown Schema Type selected!")

    def is_valid_xml(self) -> bool:
        """
        Method that checks if the given XML in this instance is valid.

        :raises ValueError: In case no validator is present.
        :return: If the XML is valid or not.
        """
        if self.schema_validator is None:
            raise ValueError("Schema Validator not known!")
        return self.schema_validator.validate(self.parsed_xml)

    @property
    def validated_xml(self) -> Optional[etree.Element]:
        """
        Only returns the XML etree Element in case the XML that was handed to the object, is valid.

        :returns: None in case of an invalid XML tree according to the schema or the etree Element.
        """
        if self.is_valid_xml():
            return self.parsed_xml
        return None
