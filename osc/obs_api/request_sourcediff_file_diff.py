from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestSourcediffFileDiff(XmlModel):
    XML_TAG = "diff"

    lines: int = Field(
        xml_attribute=True,
    )

    text: str = Field(
        xml_set_text=True,
    )
