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
        return cls.from_file(response, apiurl=apiurl)

    def to_api(self, apiurl, *, project=None):
        project = project or self.name
        url_path = ["source", project, "_meta"]
        url_query = {}
        response = self.xml_request("PUT", apiurl, url_path, url_query, data=self.to_string())
        return Status.from_file(response, apiurl=apiurl)

    def resolve_repository_flags(self, package_obj=None):
        """
        Resolve the `build`, `debuginfo`, `publish` and `useforbuild` flags
        and return their values for each repository and build arch.

        :returns: {(repo_name, repo_buildarch): {flag_name: bool} for all available repos
        """
        result = {}
        flag_names = ("build", "debuginfo", "publish", "useforbuild")

        # populate the result matrix: {(repo, arch): {"build": None, "debuginfo": None, "publish": None, "useforbuild": None}}
        for repo_obj in self.repository_list or []:
            for arch in repo_obj.arch_list or []:
                result[(repo_obj.name, arch)] = dict([(flag_name, None) for flag_name in flag_names])

        for flag_name in flag_names:
            flag_objects = getattr(self, f"{flag_name}_list") or []
            if package_obj is not None:
                flag_objects += getattr(package_obj, f"{flag_name}_list") or []

            for flag_obj in flag_objects:
                # look up entries matching the current flag and change their values according to the flag's tag
                for (entry_repo, entry_arch), entry_data in result.items():
                    match = flag_obj.repository in (entry_repo, None) and flag_obj.arch in (entry_arch, None)
                    if match:
                        entry_data[flag_name] = True if flag_obj.flag == "enable" else False

        return result
