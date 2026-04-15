import osc.commandline_git


class FileCommand(osc.commandline_git.GitObsCommand):
    """
    Manage files in a package
    """

    name = "file"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
