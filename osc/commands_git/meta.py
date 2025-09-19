import osc.commandline_git


class MetaCommand(osc.commandline_git.GitObsCommand):
    """
    Manage metadata in .git/obs store
    """

    name = "meta"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
