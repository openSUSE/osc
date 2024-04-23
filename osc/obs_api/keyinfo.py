import textwrap

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .keyinfo_pubkey import KeyinfoPubkey
from .keyinfo_sslcert import KeyinfoSslcert


class Keyinfo(XmlModel):
    XML_TAG = "keyinfo"

    project: Optional[str] = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            The name of the project.
            """
        ),
    )

    pubkey_list: Optional[List[KeyinfoPubkey]] = Field(
        xml_name="pubkey",
    )

    sslcert_list: Optional[List[KeyinfoSslcert]] = Field(
        xml_name="sslcert",
    )

    @classmethod
    def from_api(cls, apiurl: str, project: str) -> "Keyinfo":
        url_path = ["source", project, "_keyinfo"]
        url_query = {}
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)


    @classmethod
    def get_pubkey_deprecated(cls, apiurl: str, project: str, *, traverse: bool = True) -> Optional[Tuple[str, str]]:
        """
        Old API for retrieving pubkey of the given ``project``. Use ``Keyinfo.from_api()`` instead if possible.

        :param traverse: If set to ``True`` and the key is not found, traverse project hierarchy for the first available key.
        :return: (project, pubkey) or None
        """
        from urllib.error import HTTPError
        from ..connection import http_request
        from ..core import makeurl
        from ..output import print_msg

        while True:
            url_path = ["source", project, "_pubkey"]
            url_query = {}
            url = makeurl(apiurl, url_path, url_query)
            try:
                response = http_request("GET", url)
                pubkey = response.read().decode("utf-8")
                return project, pubkey
            except HTTPError as e:
                if e.code != 404:
                    raise

                if not traverse:
                    return None

                parts = project.rsplit(":", 1)
                if parts[0] != project:
                    print_msg(f"No pubkey found in project '{project}'. Trying the parent project '{parts[0]}'...", print_to="debug")
                    project = parts[0]
                    continue

                # we're at the top level, no key found
                return None

    @classmethod
    def get_sslcert_deprecated(cls, apiurl: str, project: str, *, traverse: bool = True) -> Optional[Tuple[str, str]]:
        """
        Old API for retrieving sslcert of the given ``project``. Use ``Keyinfo.from_api()`` instead if possible.

        :param traverse: If set to ``True`` and the cert is not found, traverse project hierarchy for the first available cert.
        :return: (project, sslcert) or None
        """
        from urllib.error import HTTPError
        from ..connection import http_request
        from ..core import makeurl
        from ..output import print_msg

        while True:
            url_path = ["source", project, "_project", "_sslcert"]
            url_query = {
                "meta": 1,
            }
            url = makeurl(apiurl, url_path, url_query)
            try:
                response = http_request("GET", url)
                sslcert = response.read().decode("utf-8")
                return project, sslcert
            except HTTPError as e:
                if e.code != 404:
                    raise

                if not traverse:
                    return None

                parts = project.rsplit(":", 1)
                if parts[0] != project:
                    print_msg(f"No sslcert found in project '{project}'. Trying the parent project '{parts[0]}'...", print_to="debug")
                    project = parts[0]
                    continue

                # we're at the top level, no cert found
                return None
