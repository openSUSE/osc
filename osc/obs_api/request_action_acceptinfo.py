from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionAcceptinfo(XmlModel):
    XML_TAG = "acceptinfo"

    rev: str = Field(
        xml_attribute=True,
    )

    srcmd5: str = Field(
        xml_attribute=True,
    )

    osrcmd5: str = Field(
        xml_attribute=True,
    )

    oproject: Optional[str] = Field(
        xml_attribute=True,
    )

    opackage: Optional[str] = Field(
        xml_attribute=True,
    )

    xsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    oxsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )
