from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import

from .enums import ReleaseTriggers


class RepositoryReleasetarget(XmlModel):
    XML_TAG = "releasetarget"

    project: str = Field(
        xml_attribute=True,
    )

    repository: str = Field(
        xml_attribute=True,
    )

    trigger: Optional[ReleaseTriggers] = Field(
        xml_attribute=True,
    )
