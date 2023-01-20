import sys


def print_msg(msg, print_to="debug"):
    from .. import conf

    if print_to is None:
        return
    elif print_to == "debug":
        if conf.config["debug"]:
            print(f"DEBUG: {msg}", file=sys.stderr)
    elif print_to == "stdout":
        print(msg)
    else:
        raise ValueError(f"Invalid value of the 'print_to' option: {print_to}")


def format_msg_project_package_options(
    msg,
    project=None,
    package=None,
    dest_project=None,
    dest_package=None,
    repository=None,
    dest_repository=None,
    **options,
):
    """
    Format msg, project, package, dest_project, dest_package and options into a meaningful message
    that can be printed out directly or as a debug message.
    """
    if project and not package:
        msg += f" project '{project}'"
    else:
        msg += f" package '{project}/{package}'"

    if repository:
        msg += f" repository '{repository}'"

    if any([dest_project, dest_package, dest_repository]):
        msg += " to"

    if dest_project and not dest_package:
        msg += f" project '{dest_project}'"
    elif dest_project and dest_package:
        msg += f" package '{dest_project}/{dest_package}'"

    if dest_repository:
        msg += f" repository '{dest_repository}'"

    msg_options = [key.replace("_", "-") for key, value in options.items() if value]
    if msg_options:
        msg_options.sort()
        msg_options_str = ", ".join(msg_options)
        msg += f" options: {msg_options_str}"

    return msg
