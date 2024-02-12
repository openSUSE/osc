from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class Flag(XmlModel):
    XML_TAG = None

    def __init__(self, flag, **kwargs):
        super().__init__(flag=flag, **kwargs)

    class FlagChoices(Enum):
        ENABLE = "enable"
        DISABLE = "disable"

    flag: FlagChoices = Field(
        xml_set_tag=True,
    )

    arch: Optional[str] = Field(
        xml_attribute=True,
    )

    repository: Optional[str] = Field(
        xml_attribute=True,
    )
