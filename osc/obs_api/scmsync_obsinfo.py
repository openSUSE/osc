import typing

from ..util.models import *  # pylint: disable=wildcard-import,unused-wildcard-import


class ScmsyncObsinfo(BaseModel):
    """
    Class for handling _scmsync.obsinfo files
    """

    mtime: int = Field()
    commit: str = Field()
    url: str = Field()
    revision: str = Field()

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
    def from_api(cls, apiurl: str, project: str, package: str, *, rev: str) -> "ScmsyncObsinfo":
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
