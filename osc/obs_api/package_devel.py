from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PackageDevel(XmlModel):
    XML_TAG = "devel"

    project: str = Field(
        xml_attribute=True,
    )

    package: Optional[str] = Field(
        xml_attribute=True,
    )
