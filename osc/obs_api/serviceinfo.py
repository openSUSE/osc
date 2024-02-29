from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class Serviceinfo(XmlModel):
    XML_TAG = "serviceinfo"

    xsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    lsrcmd5: Optional[str] = Field(
        xml_attribute=True,
    )

    error: Optional[str] = Field(
        xml_attribute=True,
    )

    code: Optional[str] = Field(
        xml_attribute=True,
    )
