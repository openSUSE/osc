import osc.commandline_git


class LoginCommand(osc.commandline_git.GitObsCommand):
    """
    Manage configured credentials to Gitea servers

    Configure, list, update, and remove login authentication entries for Gitea servers.

    Examples:
        git-obs login add opensuse --url https://src.opensuse.org --user myuser
        git-obs login list
        git-obs login update opensuse --set-as-default
    """

    name = "login"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
