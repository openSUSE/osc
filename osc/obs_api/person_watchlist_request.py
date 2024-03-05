from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PersonWatchlistRequest(XmlModel):
    XML_TAG = "request"

    number: str = Field(
        xml_attribute=True,
    )
