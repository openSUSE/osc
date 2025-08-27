import osc.commandline_git


class StoreCommand(osc.commandline_git.GitObsCommand):
    """
    Manage local metadata store
    """

    name = "store"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
