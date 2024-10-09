import osc.commandline_git


class LoginCommand(osc.commandline_git.GitObsCommand):
    """
    Manage configured credentials to Gitea servers
    """

    name = "login"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
