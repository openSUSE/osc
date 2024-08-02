import osc.commandline


# GIT / GITEA


def cmd_add_login(cmd: osc.commandline.OscCommand):
    # TODO: option name? make a global option?
    cmd.add_argument(
        "-G",
        "--gitea-login-name",
        help="Name of the login entry in the config file",
    )


def cmd_add_owner(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "owner",
        help="Name of the repository owner (login, org)",
    )


def cmd_add_repo(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "repo",
        help="Name of the repository",
    )


def cmd_add_new_repo_name(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "--new-repo-name",
        help="Name of the newly forked repo",
    )


# OBS


def cmd_add_apiurl(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "-A",
        "--apiurl",
        metavar="URL",
        help="Open Build Service API URL or a configured alias",
    )


def cmd_add_project(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "project",
        help="Name of the OBS project",
    )


def cmd_add_package(cmd: osc.commandline.OscCommand):
    cmd.add_argument(
        "package",
        help="Name of the OBS package",
    )
