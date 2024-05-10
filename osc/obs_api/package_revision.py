from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PackageRevision(XmlModel):
    XML_TAG = "revision"

    rev: int = Field(
        xml_attribute=True,
    )

    vrev: Optional[str] = Field(
        xml_attribute=True,
    )

    srcmd5: str = Field(
    )

    version: str = Field(
    )

    time: int = Field(
    )

    user: str = Field(
    )

    comment: Optional[str] = Field(
    )

    requestid: Optional[int] = Field(
    )

    def get_time_str(self):
        import time
        return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.time))
