import urllib.error

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .package import Package
from .package_sources import PackageSources
from .request_action_acceptinfo import RequestActionAcceptinfo
from .request_action_group import RequestActionGroup
from .request_action_grouped import RequestActionGrouped
from .request_action_options import RequestActionOptions
from .request_action_person import RequestActionPerson
from .request_action_source import RequestActionSource
from .request_action_target import RequestActionTarget
from .request_sourcediff import RequestSourcediff


class RequestAction(XmlModel):
    XML_TAG = "action"

    class TypeEnum(str, Enum):
        SUBMIT = "submit"
        DELETE = "delete"
        CHANGE_DEVEL = "change_devel"
        ADD_ROLE = "add_role"
        SET_BUGOWNER = "set_bugowner"
        MAINTENANCE_INCIDENT = "maintenance_incident"
        MAINTENANCE_RELEASE = "maintenance_release"
        RELEASE = "release"
        GROUP = "group"

    type: TypeEnum = Field(
        xml_attribute=True,
    )

    source: Optional[RequestActionSource] = Field(
    )

    target: Optional[RequestActionTarget] = Field(
    )

    person: Optional[RequestActionPerson] = Field(
    )

    group: Optional[RequestActionGroup] = Field(
    )

    grouped_list: Optional[List[RequestActionGrouped]] = Field(
        xml_name="grouped",
    )

    options: Optional[RequestActionOptions] = Field(
    )

    sourcediff: Optional[RequestSourcediff] = Field(
    )

    acceptinfo: Optional[RequestActionAcceptinfo] = Field(
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._allow_new_attributes = True
        # source and target always come from ``self._apiurl`` while devel and factory projects may live elsewhere
        self._devel_apiurl = self._apiurl
        self._factory_apiurl = self._apiurl
        self._factory_project = "openSUSE:Factory"
        self._props = {}
        self._allow_new_attributes = False

    def _get_package(self, package_type):
        key = f"{package_type}_package"
        if key not in self._props:
            func = getattr(self, f"_get_{package_type}_apiurl_project_package")
            apiurl, project, package = func()
            if apiurl is None:
                self._props[key] = None
            else:
                try:
                    self._props[key] = Package.from_api(apiurl, project, package)
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise
                    self._props[key] = None
        return self._props[key]

    def _get_package_sources(self, package_type, *, rev=None):
        key = f"{package_type}_package_sources"
        if key not in self._props:
            func = getattr(self, f"_get_{package_type}_apiurl_project_package")
            apiurl, project, package = func()
            if apiurl is None:
                self._props[key] = None
            else:
                try:
                    self._props[key] = PackageSources.from_api(apiurl, project, package, rev=rev)
                except urllib.error.HTTPError as e:
                    if e.code != 404:
                        raise
                    self._props[key] = None
        return self._props[key]

    def _get_source_apiurl_project_package(self):
        return self._apiurl, self.source.project, self.source.package

    @property
    def source_package(self) -> Optional[Package]:
        """
        Return a ``Package`` object that encapsulates metadata of the source package.
        """
        return self._get_package("source")

    @property
    def source_package_sources(self) -> Optional[PackageSources]:
        """
        Return a ``PackageSources`` object that contains information about the ``source.rev`` revision of the source package sources in OBS SCM.
        """
        if self.source is None:
            return None
        return self._get_package_sources("source", rev=self.source.rev)

    def _get_target_apiurl_project_package(self):
        if self.target is None:
            return None, None, None
        target_project, target_package = self.get_actual_target_project_package()
        return self._apiurl, target_project, target_package

    @property
    def target_package(self) -> Optional[Package]:
        """
        Return a ``Package`` object that encapsulates metadata of the target package.
        """
        return self._get_package("target")

    @property
    def target_package_sources(self) -> Optional[PackageSources]:
        """
        Return a ``PackageSources`` object that contains information about the current revision of the target package sources in OBS SCM.
        """
        return self._get_package_sources("target")

    def _get_factory_apiurl_project_package(self):
        if self.target is None:
            # a new package was submitted, it doesn't exist on target; let's read the package name from the source
            target_project, target_package = None, self.source.package
        else:
            target_project, target_package = self.get_actual_target_project_package()

        if (self._apiurl, target_project) == (self._factory_apiurl, self._factory_project):
            # factory package equals the target package
            return None, None, None

        return self._factory_apiurl, self._factory_project, target_package

    @property
    def factory_package(self) -> Optional[Package]:
        """
        Return a ``Package`` object that encapsulates metadata of the package in the factory project.
        The name of the package equals the target package name.
        """
        return self._get_package("factory")

    @property
    def factory_package_sources(self) -> Optional[PackageSources]:
        """
        Return a ``PackageSources`` object that contains information about the current revision of the factory package sources in OBS SCM.
        """
        return self._get_package_sources("factory")

    def _get_devel_apiurl_project_package(self):
        if self.factory_package is None:
            return None, None, None

        devel = self.factory_package.devel
        if devel is None:
            return None, None, None

        return (
            self._devel_apiurl,
            devel.project,
            devel.package or self.factory_package.name,
        )

    @property
    def devel_package(self) -> Optional[Package]:
        """
        Return a ``Package`` object that encapsulates metadata of the package in the devel project.
        The devel project name and package name come from ``self.factory_package.devel``.
        If the devel package name is not set, target package name is used.
        """
        return self._get_package("devel")

    @property
    def devel_package_sources(self) -> Optional[PackageSources]:
        """
        Return a ``PackageSources`` object that contains information about the current revision of the devel package sources in OBS SCM.
        """
        return self._get_package_sources("devel")

    def get_actual_target_project_package(self) -> Tuple[str, str]:
        """
        Return the target project and package names because maintenance incidents require special handling.

        The target project for maintenance incidents is virtual and cannot be queried.
        The actual target project is specified in target's ``releaseproject`` field.

        Also the target package for maintenance incidents is not set explicitly.
        It is extracted from ``releasename`` field from the source metadata.
        If ``releasename`` is not defined, source package name is used.
        """

        if self.type == "maintenance_incident":
            # dmach's note on security:
            # The ``releaseproject`` is baked into the target information in the request and that's perfectly ok.
            # The ``releasename`` is part of the source package metadata and *may change* after the request is created.
            # After consulting this with OBS developers, I believe this doesn't represent any security issue
            # because the project is fixed and tampering with ``releasename`` might only lead to inconsistent naming,
            # the package would still end up it the same project.

            # target.releaseproject is always set for a maintenance_incident
            assert self.target
            assert self.target.releaseproject
            project = self.target.releaseproject

            # the target package is not specified
            # we need to extract it from source package's metadata or use source package name as a fallback
            assert self.source_package
            if self.source_package.releasename:
                package = self.source_package.releasename.split(".")[0]
            else:
                package = self.source_package.name

            return project, package

        assert self.target
        assert self.target.project
        assert self.target.package
        return self.target.project, self.target.package
