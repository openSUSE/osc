from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .flag import Flag
from .group_role import GroupRole
from .person_role import PersonRole
from .project_devel import ProjectDevel
from .project_link import ProjectLink
from .project_maintenance_maintains import ProjectMaintenanceMaintains
from .repository import Repository
from .simple_flag import SimpleFlag
from .status import Status


class Project(XmlModel):
    XML_TAG = "project"

    name: str = Field(
        xml_attribute=True,
    )

    class KindEnum(str, Enum):
        STANDARD = "standard"
        MAINTENANCE = "maintenance"
        MAINTENANCE_INCIDENT = "maintenance_incident"
        MAINTENANCE_RELEASE = "maintenance_release"

    kind: Optional[KindEnum] = Field(
        xml_attribute=True,
    )

    title: str = Field(
    )

    description: str = Field(
    )

    url: Optional[str] = Field(
    )

    link_list: Optional[List[ProjectLink]] = Field(
        xml_name="link",
    )

    mountproject: Optional[str] = Field(
    )

    remoteurl: Optional[str] = Field(
    )

    scmsync: Optional[str] = Field(
    )

    devel: Optional[ProjectDevel] = Field(
    )

    person_list: Optional[List[PersonRole]] = Field(
        xml_name="person",
    )

    group_list: Optional[List[GroupRole]] = Field(
        xml_name="group",
    )

    lock: Optional[SimpleFlag] = Field(
        xml_wrapped=True,
    )

    build_list: Optional[List[Flag]] = Field(
        xml_name="build",
        xml_wrapped=True,
    )

    publish_list: Optional[List[Flag]] = Field(
        xml_name="publish",
        xml_wrapped=True,
    )

    useforbuild_list: Optional[List[Flag]] = Field(
        xml_name="useforbuild",
        xml_wrapped=True,
    )

    debuginfo_list: Optional[List[Flag]] = Field(
        xml_name="debuginfo",
        xml_wrapped=True,
    )

    binarydownload_list: Optional[List[Flag]] = Field(
        xml_name="binarydownload",
        xml_wrapped=True,
    )

    sourceaccess: Optional[SimpleFlag] = Field(
        xml_wrapped=True,
    )

    access: Optional[SimpleFlag] = Field(
        xml_wrapped=True,
    )

    maintenance_list: Optional[List[ProjectMaintenanceMaintains]] = Field(
        xml_name="maintenance",
        xml_wrapped=True,
    )

    repository_list: Optional[List[Repository]] = Field(
        xml_name="repository",
    )

    @classmethod
    def from_api(cls, apiurl, project):
        url_path = ["source", project, "_meta"]
        url_query = {}
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response)

    def to_api(self, apiurl, *, project=None):
        project = project or self.name
        url_path = ["source", project, "_meta"]
        url_query = {}
        response = self.xml_request("PUT", apiurl, url_path, url_query, data=self.to_string())
        return Status.from_file(response)
