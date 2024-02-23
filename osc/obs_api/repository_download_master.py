from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RepositoryDownloadMaster(XmlModel):
    XML_TAG = "master"

    url: str = Field(
        xml_attribute=True,
    )

    sslfingerprint: Optional[str] = Field(
        xml_attribute=True,
    )
