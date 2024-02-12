from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class SimpleFlag(XmlModel):
    XML_TAG = None
    XML_TAG_FIELD = "flag"

    def __init__(self, flag):
        super().__init__(flag=flag)

    class SimpleFlagChoices(Enum):
        ENABLE = "enable"
        DISABLE = "disable"

    flag: SimpleFlagChoices = Field(
        xml_wrapped=True,
        xml_set_tag=True,
    )

    def __eq__(self, other):
        if hasattr(other, "flag"):
            return self.flag == other.flag
        # allow comparing with a string
        return self.flag == other
