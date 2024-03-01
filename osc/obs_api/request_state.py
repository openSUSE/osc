from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .enums import RequestStates


class RequestState(XmlModel):
    XML_TAG = "state"

    name: RequestStates = Field(
        xml_attribute=True,
    )

    who: Optional[str] = Field(
        xml_attribute=True,
    )

    when: Optional[str] = Field(
        xml_attribute=True,
    )

    created: Optional[str] = Field(
        xml_attribute=True,
    )

    superseded_by: Optional[int] = Field(
        xml_attribute=True,
    )

    approver: Optional[str] = Field(
        xml_attribute=True,
    )

    comment: Optional[str] = Field(
    )
