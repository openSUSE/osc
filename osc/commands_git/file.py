import osc.commandline_git


class FileCommand(osc.commandline_git.GitObsCommand):
    """
    Manage metadata files in a repo
    """

    name = "file"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
