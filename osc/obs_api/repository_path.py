from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RepositoryPath(XmlModel):
    XML_TAG = "path"

    project: str = Field(
        xml_attribute=True,
    )

    repository: str = Field(
        xml_attribute=True,
    )
