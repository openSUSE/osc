from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionGroup(XmlModel):
    XML_TAG = "group"

    name: str = Field(
        xml_attribute=True,
    )

    role: Optional[str] = Field(
        xml_attribute=True,
    )
