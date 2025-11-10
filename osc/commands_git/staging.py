import osc.commandline_git


class StagingCommand(osc.commandline_git.GitObsCommand):
    """
    Manage staging projects
    """

    name = "staging"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()