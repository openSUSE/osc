from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class ProjectMaintenanceMaintains(XmlModel):
    XML_TAG = "maintains"

    project: str = Field(
        xml_attribute=True,
    )
