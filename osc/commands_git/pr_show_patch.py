import osc.commandline_git


class PullRequestShowPatchCommand(osc.commandline_git.GitObsCommand):
    """
    Show patch associated to the specified pull request
    """

    name = "show-patch"
    parent = "PullRequestCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_pr

        self.add_argument_owner_repo_pull().completer = complete_pr

    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()

        owner, repo, pull = args.owner_repo_pull
        patch = gitea_api.PullRequest.get_patch(self.gitea_conn, owner, repo, pull)
        patch = highlight_diff(patch)
        print(patch.decode("utf-8"))
