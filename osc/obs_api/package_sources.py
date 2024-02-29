from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import
from .linkinfo import Linkinfo
from .package_sources_file import PackageSourcesFile
from .serviceinfo import Serviceinfo


class PackageSources(XmlModel):
    XML_TAG = "directory"

    name: str = Field(
        xml_attribute=True,
    )

    rev: str = Field(
        xml_attribute=True,
    )

    vrev: Optional[str] = Field(
        xml_attribute=True,
    )

    srcmd5: str = Field(
        xml_attribute=True,
    )

    linkinfo: Optional[Linkinfo] = Field(
    )

    serviceinfo: Optional[Serviceinfo] = Field(
    )

    file_list: Optional[List[PackageSourcesFile]] = Field(
        xml_name="entry",
    )

    @classmethod
    def from_api(
        cls,
        apiurl: str,
        project: str,
        package: str,
        *,
        deleted: Optional[bool] = None,
        expand: Optional[bool] = None,
        meta: Optional[bool] = None,
        rev: Optional[str] = None,
    ):
        """
        :param deleted: Set to ``True`` to list source files of a deleted package.
                        Throws 400: Bad Request if such package exists.
        :param expand: Expand links.
        :param meta: Set to ``True`` to list metadata file (``_meta``) instead of the sources.
        :param rev: Show sources of the specified revision.
        """
        from ..core import revision_is_empty

        if revision_is_empty(rev):
            rev = None

        url_path = ["source", project, package]
        url_query = {
            "deleted": deleted,
            "expand": expand,
            "meta": meta,
            "rev": rev,
        }
        response = cls.xml_request("GET", apiurl, url_path, url_query)
        return cls.from_file(response, apiurl=apiurl)
