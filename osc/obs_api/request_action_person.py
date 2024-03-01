from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionPerson(XmlModel):
    XML_TAG = "person"

    name: str = Field(
        xml_attribute=True,
    )

    role: Optional[str] = Field(
        xml_attribute=True,
    )
