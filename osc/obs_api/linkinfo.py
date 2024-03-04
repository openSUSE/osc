from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class Linkinfo(XmlModel):
    XML_TAG = "linkinfo"

    project: str = Field(
        xml_attribute=True,
    )

    package: str = Field(
        xml_attribute=True,
    )

    lsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    xsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    baserev: Optional[str] = Field(
        xml_attribute=True,
    )

    rev: Optional[str] = Field(
        xml_attribute=True,
    )

    srcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    error: Optional[str] = Field(
        xml_attribute=True,
    )

    missingok: Optional[bool] = Field(
        xml_attribute=True,
    )
