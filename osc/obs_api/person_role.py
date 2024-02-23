from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .enums import LocalRole


class PersonRole(XmlModel):
    XML_TAG = "person"

    userid: str = Field(
        xml_attribute=True,
    )

    role: LocalRole = Field(
        xml_attribute=True,
    )
