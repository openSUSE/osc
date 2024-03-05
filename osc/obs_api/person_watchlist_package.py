from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PersonWatchlistPackage(XmlModel):
    XML_TAG = "package"

    name: str = Field(
        xml_attribute=True,
    )

    project: str = Field(
        xml_attribute=True,
    )
