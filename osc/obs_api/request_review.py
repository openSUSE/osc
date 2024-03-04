from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .enums import RequestStates
from .request_review_history import RequestReviewHistory


class RequestReview(XmlModel):
    XML_TAG = "review"

    state: RequestStates = Field(
        xml_attribute=True,
    )

    created: Optional[str] = Field(
        xml_attribute=True,
    )

    by_user: Optional[str] = Field(
        xml_attribute=True,
    )

    by_group: Optional[str] = Field(
        xml_attribute=True,
    )

    by_project: Optional[str] = Field(
        xml_attribute=True,
    )

    by_package: Optional[str] = Field(
        xml_attribute=True,
    )

    who: Optional[str] = Field(
        xml_attribute=True,
    )

    when: Optional[str] = Field(
        xml_attribute=True,
    )

    comment: Optional[str] = Field(
    )

    history_list: Optional[List[RequestReviewHistory]] = Field(
        xml_name="history",
    )

    def get_user_and_type(self):
        if self.by_user:
            return (self.by_user, "user")
        if self.by_group:
            return (self.by_group, "group")
        if self.by_package:
            return (f"{self.by_project}/{self.by_package}", "package")
        if self.by_project:
            return (self.by_project, "project")
        raise RuntimeError("Unable to determine user and its type")
