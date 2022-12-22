"""
This represents the functionality needed by "osc token" and makes it available conveniently also for Python API
consumers.

.. note:: API both on the server side and here in this module are in beta status and thus subject to change!
"""

from dataclasses import dataclass
from typing import Optional, List
from lxml import etree

from osc import core, conf
from osc._private.response import parse_status
from osc._private.xml import retrieve_xml_document, XmlParser, XmlSchemaType
from osc.connection import http_POST, http_DELETE


@dataclass
class Token:
    """
    This dataclass keeps track of an "osc Token". If you desire to perform actions with this please have a look at
    :func:`~osc.core.TokenOperations`.
    """

    id = ""
    string = ""
    kind = ""
    description = ""
    triggered_at = ""
    project = ""
    package = ""

    @staticmethod
    def form_xml_node(xml_entry: etree.Element) -> "Token":
        """
        Accepts a given etree Element and converts it to a Token instance.

        :param xml_entry: The XML node that should be used. Must be already validated.
        :return: The Token instance.
        """
        result = Token()
        result.id = xml_entry.get("id")
        result.kind = xml_entry.get("kind")
        result.description = xml_entry.get("description")
        result.triggered_at = xml_entry.get("triggered_at")
        project = xml_entry.get("project", None)
        if project is not None:
            result.project = project
        package = xml_entry.get("package", None)
        if package is not None:
            result.package = package
        return result


class TokenOperations:
    """
    This class represents an OBS Token.

    For more information visit:
    https://openbuildservice.org/help/manuals/obs-user-guide/cha.obs.authorization.token.html#id-1.5.10.18.4
    """

    def __init__(self, apiurl: str):
        self.apiurl = apiurl
        self.url_path = ["person", conf.get_apiurl_usr(self.apiurl), "token"]

    def create(
        self,
        operation: str,
        project: Optional[str] = None,
        package: Optional[str] = None,
        scm_token: Optional[str] = None,
    ) -> Token:
        """
        Creates a token.

        :param operation: The operation that the token should be used for.
        :param project: The project that the token should be used for. If not given, the token has no scope.
        :param package: The package that the token should be used for. If not given, the token has no scope.
        :param scm_token: The token that was handed by the SCM service (e.g. GitHub).
        :raises ValueError: In case the creation of the token was not successful.
        :return: The Token object with its secret and ID.
        """
        result = Token()
        if operation == "workflow" and not scm_token:
            raise ValueError('If operation="workflow" scm_token="<token>" option is required!')
        query = {"cmd": "create"}
        if operation:
            query["operation"] = operation
        if scm_token:
            query["scm_token"] = scm_token
        if project and package:
            query["project"] = project
            query["package"] = package

        url = core.makeurl(self.apiurl, self.url_path, query)
        result_xml = retrieve_xml_document(url)
        status = parse_status(result_xml)
        if status.summary == "ok":
            for element in status.data:
                if element.get("name") == "token":
                    result.string = element.text
                if element.get("name") == "id":
                    result.id = element.text
            return result
        raise ValueError(status.summary)

    def delete(self, token_id: str):
        """
        Deletes a given token from the authenticated account.

        :param token_id: The token ID for the token that should be deleted.
        """
        self.url_path.append(token_id)
        url = core.makeurl(self.apiurl, self.url_path)
        xml_document = retrieve_xml_document(url, http_DELETE)
        status = parse_status(xml_document)
        if status.summary.lower() == "ok":
            # We have no guarantee about the casing of the status,
            # and we don't have access to the attribute on the root node.
            return
        raise ValueError(status.summary)

    def list(self) -> List[Token]:
        """
        Lists all tokens that are available to the user.

        :raises ValueError: In case the list of tokens retrieved from the OBS instance could not be parsed correctly.
        :return: The list of tokens that could be parsed from the result.
        """
        result: List[Token] = []
        url = core.makeurl(self.apiurl, self.url_path)
        token_xml = retrieve_xml_document(url)
        list_parser = XmlParser(token_xml)
        list_parser.retrieve_validator(XmlSchemaType.RELAXNG, "https://build.opensuse.org/schema/tokenlist.rng")
        root = list_parser.validated_xml
        if root is None:
            raise ValueError(parse_status(token_xml).summary)
        for child_element in root:
            result.append(Token.form_xml_node(child_element))
        return result

    def trigger(
        self, token: str, operation: str = "runservice", project: Optional[str] = None, package: Optional[str] = None
    ):
        """
        Trigger an operation in the OBS instance.

        :param token: The token that should be used to trigger the action.
        :param operation: The operation that should be triggered.
        :param project: The project scope that the action should be limited to.
        :param package: The package scope that the action should be limited to.
        :raises ValueError: In case the action is not explicitly confirmed as successful.
        """
        # TODO: Add missing query operations - https://github.com/openSUSE/osc/issues/1194
        operation = operation or "runservice"
        query = {}
        if project and package:
            query["project"] = project
            query["package"] = package
        url = core.makeurl(self.apiurl, ["trigger", operation], query)
        headers = {
            "Content-Type": "application/octet-stream",
            "Authorization": "Token " + token,
        }
        http_post_fd = http_POST(url, headers=headers)
        status = parse_status(core.decode_it(http_post_fd.read()))
        if status.summary.lower() == "ok":
            # We have no guarantee about the casing of the status,
            # and we don't have access to the attribute on the root node.
            return
        raise ValueError(status.summary)
