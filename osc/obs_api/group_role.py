from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .enums import LocalRole


class GroupRole(XmlModel):
    XML_TAG = "group"

    groupid: str = Field(
        xml_attribute=True,
    )

    role: LocalRole = Field(
        xml_attribute=True,
    )
