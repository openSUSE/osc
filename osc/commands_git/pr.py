import osc.commandline_git


# we decided not to use the command name 'pull' because that could be confused
# with the completely unrelated 'git pull' command


class PullRequestCommand(osc.commandline_git.GitObsCommand):
    """
    Manage pull requests

    Create, inspect, checkout, review, merge, and manage pull requests on Gitea.

    Examples:
        git-obs pr create --title "Fix build"
        git-obs pr checkout 42
        git-obs pr list openSUSE/curl
        git-obs pr review
    """

    name = "pr"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
