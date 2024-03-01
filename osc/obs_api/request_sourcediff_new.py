from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffNew(XmlModel):
    XML_TAG = "new"

    project: str = Field(
        xml_attribute=True,
    )

    package: str = Field(
        xml_attribute=True,
    )

    rev: str = Field(
        xml_attribute=True,
    )

    srcmd5: str = Field(
        xml_attribute=True,
    )
