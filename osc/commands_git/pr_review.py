import osc.commandline_git


# we decided not to use the command name 'pull' because that could be confused
# with the completely unrelated 'git pull' command


class PullRequestReviewCommand(osc.commandline_git.GitObsCommand):
    """
    Manage pull request reviews

    Approve, decline, cancel, or interactively review pull requests.

    Examples:
        git-obs pr review
        git-obs pr review approve openSUSE/curl#42
        git-obs pr review decline openSUSE/curl#42 -m "Changes needed"
    """

    name = "review"
    parent = "PullRequestCommand"

    def init_arguments(self):
        pass

    def run(self, args):
        self.parser.print_help()
