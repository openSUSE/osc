from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .repository_download_master import RepositoryDownloadMaster


class RepositoryDownload(XmlModel):
    XML_TAG = "download"

    arch: str = Field(
        xml_attribute=True,
    )

    url: str = Field(
        xml_attribute=True,
    )

    class RepotypeEnum(str, Enum):
        RPMMD = "rpmmd"
        SUSETAGS = "susetags"
        DEB = "deb"
        ARCH = "arch"
        MDK = "mdk"
        REGISTRY = "registry"

    repotype: RepotypeEnum = Field(
        xml_attribute=True,
    )

    archfilter: Optional[str] = Field(
    )

    master: Optional[RepositoryDownloadMaster] = Field(
    )

    pubkey: Optional[str] = Field(
    )
