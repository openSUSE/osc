from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PersonWatchlistProject(XmlModel):
    XML_TAG = "project"

    name: str = Field(
        xml_attribute=True,
    )
