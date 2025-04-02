from typing import Any

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class Attribute(XmlModel):
    name: str = Field(
        xml_attribute=True,
    )
    namespace: str = Field(
        xml_attribute=True,
    )
    value: str = Field(
        xml_set_text=True,
        xml_wrapped=True,
    )


class Attributes(XmlModel):
    XML_TAG = "attributes"

    attribute_list: List[Attribute] = Field(
        xml_name="attribute",
    )

    @classmethod
    def from_api(
        cls, apiurl: str, project: str, package: Optional[str] = None, *, attr: Optional[str] = None
    ) -> "Attributes":
        import urllib.error
        from .. import oscerr
        from ..connection import http_request
        from ..core import makeurl

        if package:
            url_path = ["source", project, package, "_attribute"]
        else:
            url_path = ["source", project, "_attribute"]

        if attr:
            url_path.append(attr)

        url_query: Dict[str, Any] = {}
        url = makeurl(apiurl, url_path, url_query)
        response = http_request("GET", url)
        return cls.from_file(response)
