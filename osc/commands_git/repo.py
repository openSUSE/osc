import osc.commandline_git


class RepoCommand(osc.commandline_git.GitObsCommand):
    """
    Manage git repos

    Manage Git repositories on Gitea: fork, clone, init, or list repositories.

    Examples:
        git-obs repo fork openSUSE/curl
        git-obs repo clone <user>/curl
        git-obs repo list --org openSUSE
    """

    name = "repo"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
