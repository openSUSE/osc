from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionSource(XmlModel):
    XML_TAG = "source"

    project: str = Field(
        xml_attribute=True,
    )

    package: Optional[str] = Field(
        xml_attribute=True,
    )

    rev: Optional[str] = Field(
        xml_attribute=True,
    )

    repository: Optional[str] = Field(
        xml_attribute=True,
    )
