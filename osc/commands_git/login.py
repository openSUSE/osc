import osc.commandline


class LoginCommand(osc.commandline.OscCommand):
    """
    Manage credentials to Gitea servers
    """

    name = "login"

    def init_arguments(self):
        pass
