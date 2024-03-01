from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffIssue(XmlModel):
    XML_TAG = "issue"

    state: str = Field(
        xml_attribute=True,
    )

    tracker: str = Field(
        xml_attribute=True,
    )

    name: str = Field(
        xml_attribute=True,
    )

    label: str = Field(
        xml_attribute=True,
    )

    url: str = Field(
        xml_attribute=True,
    )
