from . import api
from .. import oscerr


def get_configuration_value(apiurl, option):
    url_path = ["configuration"]
    url_query = {}
    root = api.get(apiurl, url_path, url_query)
    node = api.find_node(root, "configuration", option)
    if node is None or not node.text:
        raise oscerr.APIError(f"Couldn't get configuration option '{option}'")
    return node.text
