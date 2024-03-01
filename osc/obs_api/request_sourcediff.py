from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .request_sourcediff_files_file import RequestSourcediffFilesFile
from .request_sourcediff_issue import RequestSourcediffIssue
from .request_sourcediff_new import RequestSourcediffNew
from .request_sourcediff_old import RequestSourcediffOld


class RequestSourcediff(XmlModel):
    XML_TAG = "sourcediff"

    key: str = Field(
        xml_attribute=True,
    )

    old: Optional[RequestSourcediffOld] = Field(
    )

    new: Optional[RequestSourcediffNew] = Field(
    )

    files_list: List[RequestSourcediffFilesFile] = Field(
        xml_name="files",
        xml_wrapped=True,
    )

    issue_list: Optional[List[RequestSourcediffIssue]] = Field(
        xml_name="issues",
        xml_wrapped=True,
        xml_item_name="issue",
    )
