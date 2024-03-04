from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class RequestActionOptions(XmlModel):
    XML_TAG = "options"

    class SourceupdateEnum(str, Enum):
        UPDATE = "update"
        NOUPDATE = "noupdate"
        CLEANUP = "cleanup"

    sourceupdate: Optional[SourceupdateEnum] = Field(
    )

    class UpdatelinkEnum(str, Enum):
        TRUE = "true"
        FALSE = "false"

    updatelink: Optional[UpdatelinkEnum] = Field(
    )

    class MakeoriginolderEnum(str, Enum):
        TRUE = "true"
        FALSE = "false"

    makeoriginolder: Optional[MakeoriginolderEnum] = Field(
    )
