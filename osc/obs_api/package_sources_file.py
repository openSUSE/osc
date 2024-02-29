from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class PackageSourcesFile(XmlModel):
    XML_TAG = "entry"

    name: str = Field(
        xml_attribute=True,
    )

    md5: str = Field(
        xml_attribute=True,
    )

    mtime: int = Field(
        xml_attribute=True,
    )

    size: int = Field(
        xml_attribute=True,
    )

    skipped: Optional[bool] = Field(
        xml_attribute=True,
    )

    def _get_cmp_data(self):
        return (self.name, self.mtime, self.size, self.md5, self.skipped or False)
