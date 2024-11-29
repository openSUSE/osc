from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from xml.etree import ElementTree as ET


class SimpleFlag(XmlModel):
    XML_TAG = None

    def __init__(self, flag, **kwargs):
        super().__init__(flag=flag, **kwargs)

    class SimpleFlagChoices(Enum):
        ENABLE = "enable"
        DISABLE = "disable"

    flag: SimpleFlagChoices = Field(
        xml_set_tag=True,
    )

    def __eq__(self, other):
        if hasattr(other, "flag"):
            return self.flag == other.flag
        # allow comparing with a string
        return self.flag == other

    @classmethod
    def from_xml(cls, root: ET.Element, *, apiurl: Optional[str] = None):
        return cls(flag=root[0].tag)
