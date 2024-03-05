import sys


def print_msg(*args, print_to="debug"):
    from .. import conf

    if print_to is None:
        return
    elif print_to == "debug":
        # print a debug message to stderr if config["debug"] is set
        if conf.config["debug"]:
            print("DEBUG:", *args, file=sys.stderr)
    elif print_to == "verbose":
        # print a verbose message to stdout if config["verbose"] or config["debug"] is set
        if conf.config["verbose"] or conf.config["debug"]:
            print(*args)
    elif print_to == "stdout":
        # print the message to stdout
        print(*args)
    elif print_to == "stderr":
        # print the message to stderr
        print(*args, file=sys.stderr)
    else:
        raise ValueError(f"Invalid value of the 'print_to' option: {print_to}")


