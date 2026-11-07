import osc.commandline_git


class MetaCommand(osc.commandline_git.GitObsCommand):
    """
    Manage metadata in .git/obs store

    Pull, set, query, list, or reset OBS metadata in the local checkout repository.

    Examples:
        git-obs meta pull
        git-obs meta info
        git-obs meta set --apiurl https://api.opensuse.org
    """

    name = "meta"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
