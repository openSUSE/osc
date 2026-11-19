import textwrap
from datetime import datetime, timedelta, timezone

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
        APITOKEN = "apitoken"

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
            - apitoken: general API token for Bearer authentication, replaces the password
            """
        ),
    )

    triggered_at: Optional[str] = Field(
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
        if self.kind == self.Kind.APITOKEN:
            # only the hash of the secret is stored server-side; the plaintext
            # was shown once at creation time and cannot be retrieved again
            table.add("String", "(secret hash, not retrievable)", color="bold")
        else:
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

    #: Default lifetime of a newly created API token when no explicit
    #: expiry is requested.
    API_TOKEN_DEFAULT_EXPIRY_DAYS = 90

    @classmethod
    def default_expiry(cls) -> str:
        """
        ISO 8601 expiry timestamp for an API token created right now with
        the default lifetime.
        """
        return (datetime.now(timezone.utc) + timedelta(days=cls.API_TOKEN_DEFAULT_EXPIRY_DAYS)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    @classmethod
    def cmd_create_api_token(
        cls,
        apiurl: str,
        user: str,
        *,
        description: Optional[str] = None,
        expires_at: Optional[str] = None,
    ):
        """
        Create a general API token (Bearer authentication).

        Returns a ``(token_id, secret)`` tuple. The secret is only ever
        returned by this call; it cannot be retrieved afterwards.
        """
        url_path = ["person", user, "token"]
        url_query = {
            "operation": "apitoken",
            "description": description,
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query)
        status = Status.from_file(response, apiurl=apiurl)
        token_id = status.data.get("id")
        secret = status.data.get("token")
        if not token_id or not secret:
            raise ValueError("Server did not return the new API token")

        if expires_at:
            cls.do_set_attributes(apiurl, user, token_id, expires_at=expires_at)

        return token_id, secret

    @classmethod
    def do_set_attributes(
        cls,
        apiurl: str,
        user: str,
        token: str,
        *,
        expires_at: Optional[str] = None,
        description: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        from xml.sax.saxutils import quoteattr

        url_path = ["person", user, "token", token]
        url_query = {}
        attributes = ""
        if expires_at is not None:
            attributes += f" expires_at={quoteattr(expires_at)}"
        if description is not None:
            attributes += f" description={quoteattr(description)}"
        if enabled is not None:
            attributes += f" enabled={quoteattr('true' if enabled else 'false')}"
        data = f"<token{attributes} />"
        response = cls.xml_request("PUT", apiurl, url_path, url_query, data=data)
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
