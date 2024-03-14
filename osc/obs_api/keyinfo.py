import textwrap

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .keyinfo_pubkey import KeyinfoPubkey
from .keyinfo_sslcert import KeyinfoSslcert


class Keyinfo(XmlModel):
    XML_TAG = "keyinfo"

    project: str = Field(
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
