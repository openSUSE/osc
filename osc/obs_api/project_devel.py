from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class ProjectDevel(XmlModel):
    XML_TAG = "devel"

    project: str = Field(
        xml_attribute=True,
    )
