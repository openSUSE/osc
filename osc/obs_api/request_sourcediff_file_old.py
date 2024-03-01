from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffFileOld(XmlModel):
    XML_TAG = "old"

    name: str = Field(
        xml_attribute=True,
    )

    md5: str = Field(
        xml_attribute=True,
    )

    size: int = Field(
        xml_attribute=True,
    )
