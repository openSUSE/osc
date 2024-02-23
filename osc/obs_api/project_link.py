from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class ProjectLink(XmlModel):
    XML_TAG = "link"

    project: str = Field(
        xml_attribute=True,
    )

    class VrevmodeEnum(str, Enum):
        UNEXTEND = "unextend"
        EXTEND = "extend"

    vrevmode: Optional[VrevmodeEnum] = Field(
        xml_attribute=True,
    )
