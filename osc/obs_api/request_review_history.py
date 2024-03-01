from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestReviewHistory(XmlModel):
    XML_TAG = "history"

    who: str = Field(
        xml_attribute=True,
    )

    when: str = Field(
        xml_attribute=True,
    )

    description: str = Field(
    )

    comment: Optional[str] = Field(
    )
