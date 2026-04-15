import osc.commandline_git


class FileMaintainershipCommand(osc.commandline_git.GitObsCommand):
    """
    Manage the _maintainership.json file
    """

    name = "maintainership"
    parent = "FileCommand"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
