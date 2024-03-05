from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .enums import BoolString
from .person_owner import PersonOwner
from .person_watchlist import PersonWatchlist


class Person(XmlModel):
    XML_TAG = "person"

    login: str = Field(
    )

    email: Optional[str] = Field(
    )

    realname: Optional[str] = Field(
    )

    owner: Optional[PersonOwner] = Field(
    )

    state: Optional[str] = Field(
    )

    globalrole_list: Optional[List[str]] = Field(
        xml_name="globalrole",
    )

    watchlist: Optional[PersonWatchlist] = Field(
    )

    ignore_auth_services: Optional[BoolString] = Field(
    )

    @classmethod
    def from_api(cls, apiurl: str, username: str):
        url_path = ["person", username]
        url_query = {}
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)

    @classmethod
    def search(
        cls,
        apiurl: str,
        login: Optional[str] = None,
        email: Optional[str] = None,
        realname: Optional[str] = None,
        state: Optional[str] = None,
        **kwargs,
    ) -> List["Person"]:
        from xml.etree import ElementTree as ET
        from ..util.xpath import XPathQuery as Q

        url_path = ["search", "person"]
        url_query = {
            "match": Q(
                login=login,
                email=email,
                realname=realname,
                state=state,
                **kwargs,
            ),
        }
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        root = ET.parse(response).getroot()
        assert root.tag == "collection"
        result = []
        for node in root:
            result.append(cls.from_xml(node, apiurl=apiurl))
        return result
