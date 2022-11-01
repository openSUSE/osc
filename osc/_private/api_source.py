from . import api
from .common import format_msg_project_package_options
from .common import print_msg
from .. import oscerr


def add_channels(apiurl, project, package=None, enable_all=False, skip_disabled=False, print_to="debug"):
    if all((enable_all, skip_disabled)):
        raise oscerr.OscValueError("Options 'enable_all' and 'skip_disabled' are mutually exclusive")

    msg = format_msg_project_package_options(
        "Adding channels to",
        project,
        package,
        enable_all=enable_all,
        skip_disabled=skip_disabled,
    )
    print_msg(msg, print_to=print_to)

    url_path = ["source", project]
    if package:
        url_path += [package]

    url_query = {"cmd": "addchannels"}
    if enable_all:
        url_query["mode"] = "enable_all"
    if skip_disabled:
        url_query["mode"] = "skip_disabled"

    return api.post(apiurl, url_path, url_query)
