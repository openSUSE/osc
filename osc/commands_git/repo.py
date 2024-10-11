import osc.commandline_git


class RepoCommand(osc.commandline_git.GitObsCommand):
    """
    Manage git repos
    """

    name = "repo"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
