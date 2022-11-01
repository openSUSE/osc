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
        raise ValueError(f"Invalid value of the 'output' option: {output}")


def format_msg_project_package_options(msg, project=None, package=None, **options):
    """
    Format msg, project, package and options into a meaningful message
    that can be printed out directly or as a debug message.
    """
    if project:
        msg += f" project: '{project}'"

    if package:
        msg += f" package: '{package}'"

    msg_options = [key.replace("_", "-") for key, value in options.items() if value]
    if msg_options:
        msg_options.sort()
        msg_options_str = ", ".join(msg_options)
        msg += f" options: {msg_options_str}"

    return msg
