from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .enums import BlockModes
from .enums import BuildArch
from .enums import LinkedbuildModes
from .enums import RebuildModes
from .repository_download import RepositoryDownload
from .repository_hostsystem import RepositoryHostsystem
from .repository_path import RepositoryPath
from .repository_releasetarget import RepositoryReleasetarget


class Repository(XmlModel):
    XML_TAG = "repository"

    name: str = Field(
        xml_attribute=True,
    )

    rebuild: Optional[RebuildModes] = Field(
        xml_attribute=True,
    )

    block: Optional[BlockModes] = Field(
        xml_attribute=True,
    )

    linkedbuild: Optional[LinkedbuildModes] = Field(
        xml_attribute=True,
    )

    download_list: Optional[List[RepositoryDownload]] = Field(
        xml_name="download",
    )

    releasetarget_list: Optional[List[RepositoryReleasetarget]] = Field(
        xml_name="releasetarget",
    )

    hostsystem_list: Optional[List[RepositoryHostsystem]] = Field(
        xml_name="hostsystem",
    )

    path_list: Optional[List[RepositoryPath]] = Field(
        xml_name="path",
    )

    arch_list: Optional[List[BuildArch]] = Field(
        xml_name="arch",
    )
