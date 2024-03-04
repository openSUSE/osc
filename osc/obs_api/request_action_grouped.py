from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionGrouped(XmlModel):
    XML_TAG = "grouped"

    id: str = Field(
        xml_attribute=True,
    )
