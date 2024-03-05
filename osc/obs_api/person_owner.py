from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PersonOwner(XmlModel):
    XML_TAG = "owner"

    userid: str = Field(
        xml_attribute=True,
    )
