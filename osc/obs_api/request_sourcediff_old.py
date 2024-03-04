from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffOld(XmlModel):
    XML_TAG = "old"

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
