import textwrap

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .status_data import StatusData


class Status(XmlModel):
    XML_TAG = "status"

    code: str = Field(
        xml_attribute=True,
        description=textwrap.dedent(
            """
            Status code returned by the server.
            """
        ),
    )

    summary: Optional[str] = Field(
        description=textwrap.dedent(
            """
            Human readable summary.
            """
        ),
    )

    details: Optional[str] = Field(
        description=textwrap.dedent(
            """
            Detailed, human readable information.
            """
        ),
    )

    data_list: Optional[List[StatusData]] = Field(
        xml_name="data",
        description=textwrap.dedent(
            """
            Additional machine readable data.
            """
        ),
    )

    @property
    def data(self):
        result = {}
        for entry in self.data_list or []:
            key = entry.name
            value = entry.value
            result[key] = value
        return result
