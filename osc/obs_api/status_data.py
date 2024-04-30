import textwrap

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class StatusData(XmlModel):
    XML_TAG = "data"

    class NameEnum(str, Enum):
        SOURCEPROJECT = "sourceproject"
        SOURCEPACKAGE = "sourcepackage"
        TARGETPROJECT = "targetproject"
        TARGETPACKAGE = "targetpackage"
        TOKEN = "token"
        ID = "id"

    name: NameEnum = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            Key.
            """
        ),
    )

    value: str = Field(
        xml_set_text=True,
        description=textwrap.dedent(
            """
            Value.
            """
        ),
    )
