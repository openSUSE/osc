from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionTarget(XmlModel):
    XML_TAG = "target"

    project: str = Field(
        xml_attribute=True,
    )

    package: Optional[str] = Field(
        xml_attribute=True,
    )

    releaseproject: Optional[str] = Field(
        xml_attribute=True,
    )

    repository: Optional[str] = Field(
        xml_attribute=True,
    )
