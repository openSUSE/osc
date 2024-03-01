from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .enums import ObsRatings
from .request_action import RequestAction
from .request_history import RequestHistory
from .request_review import RequestReview
from .request_state import RequestState


class Request(XmlModel):
    XML_TAG = "request"

    id: Optional[str] = Field(
        xml_attribute=True,
    )

    actions: Optional[int] = Field(
        xml_attribute=True,
    )

    creator: Optional[str] = Field(
        xml_attribute=True,
    )

    action_list: List[RequestAction] = Field(
        xml_name="action",
    )

    state: Optional[RequestState] = Field(
    )

    description: Optional[str] = Field(
    )

    priority: Optional[ObsRatings] = Field(
    )

    review_list: Optional[List[RequestReview]] = Field(
        xml_name="review",
    )

    history_list: Optional[List[RequestHistory]] = Field(
        xml_name="history",
    )

    title: Optional[str] = Field(
    )

    accept_at: Optional[str] = Field(
    )

    @classmethod
    def from_api(
        cls,
        apiurl: str,
        request_id: int,
        *,
        with_history: Optional[bool] = None,
        with_full_history: Optional[bool] = None
    ) -> "Request":
        """
        Return the specified request.

        :param request_id: Id of the request.
        :param withhistory: Include the request history in the results.
        :param withfullhistory: Includes both, request and review history in the results.
        """
        url_path = ["request", request_id]
        url_query = {
            "withhistory": with_history,
            "withfullhistory": with_full_history,
        }
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)

    @classmethod
    def cmd_diff(
        cls,
        apiurl: str,
        request_id: int,
        *,
        with_issues: Optional[bool] = None,
        with_description_issues: Optional[bool] = None,
        diff_to_superseded: Optional[int] = None
    ) -> "Request":
        """
        Return the specified request including a diff of all packages in the request.

        :param request_id: Id of the request.
        :param with_issues: Include parsed issues from referenced sources in the change files.
        :param with_description_issues: Include parsed issues from request description.
        :param diff_to_superseded: Diff relatively to the given superseded request.
        """
        url_path = ["request", str(request_id)]
        url_query = {
            "cmd": "diff",
            "view": "xml",
            "withissues": with_issues,
            "withdescriptionissues": with_description_issues,
            "diff_to_superseded": diff_to_superseded,
        }
        response = cls.xml_request("POST", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)

    def get_issues(self):
        """
        Aggregate issues from action/sourcediff into a single list.
        The list may contain duplicates.

        To get any issues returned, it is crucial to load the request with the issues
        by calling ``cmd_diff()`` with appropriate arguments first.
        """
        result = []
        for action in self.action_list or []:
            if action.sourcediff is None:
                continue
            for issue in action.sourcediff.issue_list or []:
                result.append(issue)
        return result

    def cmd_create(self,
        apiurl: str,
        *,
        add_revision: Optional[bool] = None,
        enforce_branching: Optional[bool] = None,
        ignore_build_state: Optional[bool] = None,
        ignore_delegate: Optional[bool] = None,
    ):
        """
        :param add_revision: Ask the server to add revisions of the current sources to the request.
        :param ignore_build_state: Skip the build state check.
        :param ignore_delegate: Enforce a new package instance in a project which has OBS:DelegateRequestTarget set.
        """
        url_path = ["request"]
        url_query = {
            "cmd": "create",
            "addrevision": add_revision,
            "ignore_delegate": ignore_delegate,
        }
        response = self.xml_request("POST", apiurl, url_path, url_query, data=self.to_string())
        return Request.from_file(response, apiurl=apiurl)
