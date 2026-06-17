import functools
from typing import List
from typing import Optional


def get_default_base_url():
    from ..conf import config

    result = config.apiurl.replace("://api.", "://packages.")
    return result


def ignore_http_errors(func=None, *, default=None):
    """
    Decorator to ignore 4xx HTTP errors and name resolution/max retry errors.

    If an error occurs, returns the specified `default` value (defaults to `None`).
    This is needed because majority of OBS deployments don't have the new service deployed.

    Args:
        func (callable, optional): The function to wrap.
        default (any, optional): The value to return on HTTP 4xx or connection errors.

    Returns:
        callable: The decorated function or a decorator.
    """
    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from urllib.error import HTTPError

            # HACK: NameResolutionError and MaxRetryError are not available in urllib3 v1, let's ignore all exceptions in this case
            try:
                from urllib3.exceptions import NameResolutionError
            except ImportError:
                NameResolutionError = Exception

            try:
                from urllib3.exceptions import MaxRetryError
            except ImportError:
                MaxRetryError = Exception

            try:
                try:
                    response = f(*args, **kwargs)
                except HTTPError as e:
                    if 400 <= e.status < 500:
                        return default
                    raise

                if hasattr(response, "status") and 400 <= response.status < 500:
                    return default

                return response

            except (NameResolutionError, MaxRetryError):
                return default

        return wrapper

    if func is None:
        return decorator
    else:
        return decorator(func)


@ignore_http_errors(default=[])
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


@ignore_http_errors(default=[])
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


@ignore_http_errors(default=[])
def gitea_cache_search_package_maintainers(
    base_url: Optional[str] = None,
    users: Optional[List[str]] = None,
    users__like: Optional[List[str]] = None,
    packages: Optional[List[str]] = None,
    packages__like: Optional[List[str]] = None,
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
        "package__name": packages,
        "package__name__like": packages__like,
        "package__project__name": projects,
        "package__project__name__like": projects__like,
    }
    url = makeurl(base_url, ["api", "v1", "package", "maintainer", "search"], q)
    response = http_request("GET", url)
    return response.json()


@ignore_http_errors(default=[])
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


@ignore_http_errors(default={})
def gitea_cache_maintained(
    *,
    package: str,
    base_url: Optional[str] = None,
):
    from ..core import http_request
    from ..core import makeurl

    if not base_url:
        base_url = get_default_base_url()

    q = {}
    url = makeurl(base_url, ["api", "v1", "maintained", package], q)
    response = http_request("GET", url)
    return response.json()
