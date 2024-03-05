from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .person_watchlist_package import PersonWatchlistPackage
from .person_watchlist_project import PersonWatchlistProject
from .person_watchlist_request import PersonWatchlistRequest


class PersonWatchlist(XmlModel):
    XML_TAG = "watchlist"

    project_list: Optional[List[PersonWatchlistProject]] = Field(
        xml_name="project",
    )

    package_list: Optional[List[PersonWatchlistPackage]] = Field(
        xml_name="package",
    )

    request_list: Optional[List[PersonWatchlistRequest]] = Field(
        xml_name="request",
    )
