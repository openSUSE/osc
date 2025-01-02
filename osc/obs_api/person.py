from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .enums import BoolString
from .person_owner import PersonOwner
from .person_watchlist import PersonWatchlist
from .status import Status


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

    def to_human_readable_string(self) -> str:
        """
        Render the object as a human readable string.
        """
        from ..output import KeyValueTable

        table = KeyValueTable()
        table.add("Login", self.login, color="bold")
        table.add("Real name", self.realname)
        table.add("Email", self.email)
        table.add("State", self.state)
        return f"{table}"

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
        from ..util.xml import xml_parse
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
        root = xml_parse(response).getroot()
        assert root.tag == "collection"
        result = []
        for node in root:
            result.append(cls.from_xml(node, apiurl=apiurl))
        return result

    @classmethod
    def cmd_register(
        cls,
        apiurl: str,
        *,
        login: str,
        realname: str,
        email: str,
        password: str,
        note: Optional[str] = None,
        state: Optional[str] = "confirmed",
    ):
        person = UnregisteredPerson(login=login, realname=realname, email=email, password=password, note=note, state=state)
        url_path = ["person"]
        url_query = {
            "cmd": "register",
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query, data=person.to_string())
        return Status.from_file(response, apiurl=apiurl)


class UnregisteredPerson(XmlModel):
    XML_TAG = "unregisteredperson"

    login: str = Field(
    )

    realname: str = Field(
    )

    email: str = Field(
    )

    password: str = Field(
    )

    note: Optional[str] = Field(
    )

    state: Optional[str] = Field(
    )
