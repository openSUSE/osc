import typing
import urllib.parse

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class ScmsyncObsinfo(BaseModel):
    """
    Class for handling _scmsync.obsinfo files
    """

    # the fields are defined in obs_scm_bridge in ObsGit.write_obsinfo()
    # https://github.com/openSUSE/obs-scm-bridge/blob/main/obs_scm_bridge
    mtime: int = Field()
    commit: str = Field()
    url: Optional[str] = Field()
    revision: Optional[str] = Field()
    subdir: Optional[str] = Field()
    projectscmsync: Optional[str] = Field()

    @classmethod
    def from_string(cls, data: str) -> "ScmsyncObsinfo":
        kwargs = {}
        for line in data.splitlines():
            line = line.strip()
            if not line:
                continue
            key, value = line.split(": ", 1)
            field = cls.__fields__.get(key, None)
            if field and field.type is int:
                value = int(value)
            kwargs[key] = value
        return cls(**kwargs)

    @classmethod
    def from_file(cls, file: Union[str, typing.IO]) -> "ScmsyncObsinfo":
        if isinstance(file, str):
            with open(file, "r", encoding="utf-8") as f:
                return cls.from_string(f.read())
        data = file.read()
        if isinstance(data, bytes):
            data = data.decode("utf-8")
        return cls.from_string(data)

    @classmethod
    def from_api(cls, apiurl: str, project: str, package: str, *, rev: Optional[str] = None) -> "ScmsyncObsinfo":
        import urllib.error
        from .. import oscerr
        from ..connection import http_request
        from ..core import makeurl

        url_path = ["source", project, package, "_scmsync.obsinfo"]
        url_query = {"rev": rev}
        url = makeurl(apiurl, url_path, url_query)
        try:
            response = http_request("GET", url)
        except urllib.error.HTTPError as e:
            if e.status == 404:
                raise oscerr.NotFoundAPIError(f"File '_scmsync.obsinfo' was not found in {project}/{package}, rev={rev}")
            raise
        return cls.from_file(response)


    @property
    def scm_url(self):
        """
        scm_url for obs-scm-bridge
        """
        parsed_url = list(urllib.parse.urlparse(self.url))
        query = urllib.parse.parse_qs(parsed_url[4])

        if self.subdir:
            query["subdir"] = self.subdir

        parsed_url[4] = urllib.parse.urlencode(query)

        if self.revision:
            # set revision as fragment
            parsed_url[5] = self.revision

        return urllib.parse.urlunparse(parsed_url)
