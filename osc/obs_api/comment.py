from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class Comment(XmlModel):
    XML_TAG = "comment"

    id: int = Field(
        xml_attribute=True,
    )

    who: str = Field(
        xml_attribute=True,
    )

    when: str = Field(
        xml_attribute=True,
    )

    text: str = Field(
        xml_set_text=True,
    )


class RequestComments(XmlModel):
    XML_TAG = "comments"

    request: int = Field(
        xml_attribute=True,
    )

    comment_list: Optional[List[Comment]] = Field()

    @classmethod
    def from_api(cls, apiurl: str, request: int) -> "Keyinfo":
        url_path = ["comments", "request", str(request)]
        url_query = {}
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)
