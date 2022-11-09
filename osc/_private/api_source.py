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


def add_containers(apiurl, project, package, extend_package_names=False, print_to="debug"):
    msg = format_msg_project_package_options(
        "Adding containers to",
        project,
        package,
        extend_package_names=extend_package_names,
    )
    print_msg(msg, print_to=print_to)

    url_path = ["source", project, package]

    url_query = {"cmd": "addcontainers"}
    if extend_package_names:
        url_query["extend_package_names"] = "1"

    return api.post(apiurl, url_path, url_query)


def enable_channels(apiurl, project, package=None, print_to="debug"):
    msg = format_msg_project_package_options(
        "Enabling channels in",
        project,
        package,
    )
    print_msg(msg, print_to=print_to)

    url_path = ["source", project]
    if package:
        url_path += [package]

    if package:
        url_query = {"cmd": "enablechannel"}
    else:
        url_query = {"cmd": "modifychannels", "mode": "enable_all"}

    return api.post(apiurl, url_path, url_query)


def get_linked_packages(apiurl, project, package):
    url_path = ["source", project, package]
    url_query = {"cmd": "showlinked"}
    root = api.post(apiurl, url_path, url_query)

    result = []
    nodes = api.find_nodes(root, "collection", "package")
    for node in nodes:
        item = {
            "project": node.get("project"),
            "name": node.get("name"),
        }
        result.append(item)
    return result
