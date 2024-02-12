from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RepositoryHostsystem(XmlModel):
    XML_TAG = "hostsystem"

    repository: str = Field(
        xml_attribute=True,
    )

    project: str = Field(
        xml_attribute=True,
    )
