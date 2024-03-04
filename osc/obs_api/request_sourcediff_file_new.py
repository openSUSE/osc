from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffFileNew(XmlModel):
    XML_TAG = "new"

    name: str = Field(
        xml_attribute=True,
    )

    md5: str = Field(
        xml_attribute=True,
    )

    size: int = Field(
        xml_attribute=True,
    )
