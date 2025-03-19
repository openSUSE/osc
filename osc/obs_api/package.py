from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .flag import Flag
from .group_role import GroupRole
from .package_devel import PackageDevel
from .package_revision import PackageRevision
from .person_role import PersonRole
from .simple_flag import SimpleFlag
from .status import Status


class Package(XmlModel):
    XML_TAG = "package"

    name: str = Field(
        xml_attribute=True,
    )

    project: str = Field(
        xml_attribute=True,
    )

    title: Optional[str] = Field()

    description: Optional[str] = Field()

    devel: Optional[PackageDevel] = Field()

    releasename: Optional[str] = Field()

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

    binarydownload: Optional[SimpleFlag] = Field()

    sourceaccess: Optional[SimpleFlag] = Field()

    url: Optional[str] = Field()

    scmsync: Optional[str] = Field()

    bcntsynctag: Optional[str] = Field()

    @classmethod
    def from_api(cls, apiurl, project, package, *, rev=None):
        # ``rev`` is metadata revision, not revision of the source code
        url_path = ["source", project, package, "_meta"]
        url_query = {
            "rev": rev,
        }
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)

    def to_api(self, apiurl, *, project=None, package=None):
        project = project or self.project
        package = package or self.name
        url_path = ["source", project, package, "_meta"]
        url_query = {}
        response = self.xml_request("PUT", apiurl, url_path, url_query, data=self.to_string())
        return Status.from_file(response, apiurl=apiurl)

    @classmethod
    def cmd_fork(
        cls,
        apiurl: str,
        project: str,
        package: str,
        *,
        scmsync: str,
        target_project: Optional[str] = None,
        target_package: Optional[str] = None,
    ):
        """
        POST /source/{project}/{package}?cmd=fork&scmsync={scmsync}
        For a package managed in Git.

        :param apiurl: Full apiurl or its alias.
        :param project: Project name.
        :param package: Package name.
        :param scmsync: Checkout Git URL. Example: https://src.example.com/owner/repo#branch
        :param target_project: Target project name (defaults to home:$user:branches)
        :param target_package: Target package name (defaults to $package)
        """

        url_path = ["source", project, package]
        url_query = {
            "cmd": "fork",
            "scmsync": scmsync,
            "target_project": target_project,
            "target_package": target_package,
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query)
        return Status.from_file(response, apiurl=apiurl)

    @classmethod
    def cmd_release(
        cls,
        apiurl: str,
        project: str,
        package: str,
        *,
        repository: Optional[str] = None,
        arch: Optional[str] = None,
        target_project: Optional[str] = None,
        target_repository: Optional[str] = None,
        setrelease: Optional[str] = None,
        nodelay: Optional[bool] = None,
    ):
        """
        POST /source/{project}/{package}?cmd=release
        Release sources and binaries of a specified package.

        :param apiurl: Full apiurl or its alias.
        :param project: Project name.
        :param package: Package name.
        :param repository: Limit the release to the given repository.
        :param arch: Limit the release to the given architecture.
        :param target_project: The name of the release target project.
        :param target_repository: The name of the release target repository.
        :param setrelease: Tag the release with the given value.
        :param nodelay: Do not delay the relase. If not set, the release will be delayed to be done later.
        """

        url_path = ["source", project, package]
        url_query = {
            "cmd": "release",
            "repository": repository,
            "arch": arch,
            "target_project": target_project,
            "target_repository": target_repository,
            "setrelease": setrelease,
            "nodelay": nodelay,
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query)
        return Status.from_file(response, apiurl=apiurl)

    @classmethod
    def get_revision_list(cls, apiurl: str, project: str, package: str, deleted: Optional[bool] = None, meta: Optional[bool] = None):
        from ..util.xml import xml_parse

        url_path = ["source", project, package, "_history"]
        url_query = {
            "meta": meta,
            "deleted": deleted,
        }
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        root = xml_parse(response).getroot()
        assert root.tag == "revisionlist"
        result = []
        for node in root:
            result.append(PackageRevision.from_xml(node, apiurl=apiurl))
        return result
