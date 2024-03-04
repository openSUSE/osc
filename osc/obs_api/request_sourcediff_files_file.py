from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .request_sourcediff_file_diff import RequestSourcediffFileDiff
from .request_sourcediff_file_new import RequestSourcediffFileNew
from .request_sourcediff_file_old import RequestSourcediffFileOld


class RequestSourcediffFilesFile(XmlModel):
    XML_TAG = "file"

    state: str = Field(
        xml_attribute=True,
    )

    old: Optional[RequestSourcediffFileOld] = Field(
    )

    new: Optional[RequestSourcediffFileNew] = Field(
    )

    diff: RequestSourcediffFileDiff = Field(
    )
