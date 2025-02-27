import textwrap

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .status import Status


class Token(XmlModel):
    XML_TAG = "entry"

    id: int = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            The unique id of this token.
            """
        ),
    )

    string: str = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            The token secret. This string can be used instead of the password to
            authenticate the user or to trigger service runs via the
            `POST /trigger/runservice` route.
            """
        ),
    )

    description: Optional[str] = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            This attribute can be used to identify a token from the list of tokens
            of a user.
            """
        ),
    )

    class TrueFalse(str, Enum):
        TRUE = "true"
        FALSE = "false"

    enabled: Optional[TrueFalse] = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            Indicates whether a token can accept trigger requests or not.
            """
        ),
    )

    project: Optional[str] = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            If this token is bound to a specific package, then the packages'
            project is available in this attribute.
            """
        ),
    )

    package: Optional[str] = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            The package name to which this token is bound, if it has been created
            for a specific package. Otherwise this attribute and the project
            attribute are omitted.
            """
        ),
    )

    class Kind(str, Enum):
        RSS = "rss"
        REBUILD = "rebuild"
        RELEASE = "release"
        RUNSERVICE = "runservice"
        WIPE = "wipe"
        WORKFLOW = "workflow"

    kind: Kind = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            This attribute specifies which actions can be performed via this token.
            - rss: used to retrieve the notification RSS feed
            - rebuild: trigger rebuilds of packages
            - release: trigger project releases
            - runservice: run a service via the POST /trigger/runservice route
            - wipe: trigger wipe of binary artifacts
            - workflow: trigger SCM/CI workflows, see https://openbuildservice.org/help/manuals/obs-user-guide/cha.obs.scm_ci_workflow_integration.html
            """
        ),
    )

    triggered_at: str = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            The date and time a token got triggered the last time.
            """
        ),
    )

    def to_human_readable_string(self) -> str:
        """
        Render the object as a human readable string.
        """
        from ..output import KeyValueTable

        table = KeyValueTable()
        table.add("ID", str(self.id))
        table.add("String", self.string, color="bold")
        table.add("Operation", self.kind)
        table.add("Description", self.description)
        # defaults to "true", because all tokens were enabled before introducing the "enabled" field
        table.add("Enabled", self.enabled or "true")
        table.add("Project", self.project)
        table.add("Package", self.package)
        table.add("Triggered at", self.triggered_at)
        return f"{table}"

    @classmethod
    def do_list(cls, apiurl: str, user: str):
        from ..util.xml import xml_parse

        url_path = ["person", user, "token"]
        url_query = {}
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        root = xml_parse(response).getroot()
        assert root.tag == "directory"
        result = []
        for node in root:
            result.append(cls.from_xml(node, apiurl=apiurl))
        return result

    @classmethod
    def cmd_create(
        cls,
        apiurl: str,
        user: str,
        *,
        operation: Optional[str] = None,
        project: Optional[str] = None,
        package: Optional[str] = None,
        scm_token: Optional[str] = None,
    ):
        if operation == "workflow" and not scm_token:
            raise ValueError('``operation`` = "workflow" requires ``scm_token``')

        url_path = ["person", user, "token"]
        url_query = {
            "cmd": "create",
            "operation": operation,
            "project": project,
            "package": package,
            "scm_token": scm_token,
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query)
        return Status.from_file(response, apiurl=apiurl)

    @classmethod
    def do_delete(cls, apiurl: str, user: str, token: str):
        url_path = ["person", user, "token", token]
        url_query = {}
        response = cls.xml_request("DELETE", apiurl, url_path, url_query)
        return Status.from_file(response, apiurl=apiurl)

    @classmethod
    def do_trigger(
        cls,
        apiurl: str,
        token: str,
        *,
        operation: Optional[str] = None,
        project: Optional[str] = None,
        package: Optional[str] = None,
        repo: Optional[str] = None,
        arch: Optional[str] = None,
        target_project: Optional[str] = None,
        target_repo: Optional[str] = None,
        set_release: Optional[str] = None,
    ):
        if operation:
            url_path = ["trigger", operation]
        else:
            url_path = ["trigger"]

        url_query = {
            "project": project,
            "package": package,
            "repository": repo,
            "architecture": arch,
            "targetproject": target_project,
            "targetrepository": target_repo,
            "setrelease": set_release,
        }

        headers = {
            "Content-Type": "application/octet-stream",
            "Authorization": f"Token {token}",
        }

        response = cls.xml_request("POST", apiurl, url_path, url_query, headers=headers)
        return Status.from_file(response, apiurl=apiurl)
