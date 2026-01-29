import functools
from typing import List
from typing import Optional


def get_default_base_url():
    from ..conf import config

    result = config.apiurl.replace("://api.", "://packages.")
    return result


def ignore_http_errors(func):
    """
    Return [] if `base_url` host is not found or doesn't return the expected status.
    This is needed because majority of OBS deployments don't have the new service for searching.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        from urllib3.exceptions import NameResolutionError, MaxRetryError

        try:
            response = func(*args, **kwargs)

            if hasattr(response, "status") and 400 <= response.status < 500:
                return []

            return response

        except (NameResolutionError, MaxRetryError):
            return []

    return wrapper


@ignore_http_errors
def gitea_cache_search_packages(
    base_url: Optional[str] = None,
    names: Optional[List[str]] = None,
    names__like: Optional[List[str]] = None,
    projects: Optional[List[str]] = None,
    projects__like: Optional[List[str]] = None,
):
    from ..core import http_request
    from ..core import makeurl

    if not base_url:
        base_url = get_default_base_url()

    q = {
        "name": names,
        "name__like": names__like,
        "project__name": projects,
        "project__name__like": projects__like,
    }
    url = makeurl(base_url, ["api", "v1", "package", "search"], q)
    response = http_request("GET", url)
    return response.json()


@ignore_http_errors
def gitea_cache_search_projects(
    base_url: Optional[str] = None,
    names: Optional[List[str]] = None,
    names__like: Optional[List[str]] = None,
    packages: Optional[List[str]] = None,
    packages__like: Optional[List[str]] = None,
):
    from ..core import http_request
    from ..core import makeurl

    if not base_url:
        base_url = get_default_base_url()

    q = {
        "name": names,
        "name__like": names__like,
        "packages__name": packages,
        "packages__name__like": packages__like,
    }
    url = makeurl(base_url, ["api", "v1", "project", "search"], q)
    response = http_request("GET", url)
    return response.json()


@ignore_http_errors
def gitea_cache_search_package_maintainers(
    base_url: Optional[str] = None,
    users: Optional[List[str]] = None,
    users__like: Optional[List[str]] = None,
    packages: Optional[List[str]] = None,
    packages__like: Optional[List[str]] = None,
):
    from ..core import http_request
    from ..core import makeurl

    if not base_url:
        base_url = get_default_base_url()

    q = {
        "user": users,
        "user__like": users__like,
        "packages__name": packages,
        "packages__name__like": packages__like,
    }
    url = makeurl(base_url, ["api", "v1", "package", "maintainer", "search"], q)
    response = http_request("GET", url)
    return response.json()


@ignore_http_errors
def gitea_cache_search_project_maintainers(
    base_url: Optional[str] = None,
    users: Optional[List[str]] = None,
    users__like: Optional[List[str]] = None,
    projects: Optional[List[str]] = None,
    projects__like: Optional[List[str]] = None,
):
    from ..core import http_request
    from ..core import makeurl

    if not base_url:
        base_url = get_default_base_url()

    q = {
        "user": users,
        "user__like": users__like,
        "project__name": projects,
        "project__name__like": projects__like,
    }
    url = makeurl(base_url, ["api", "v1", "project", "maintainer", "search"], q)
    response = http_request("GET", url)
    return response.json()
