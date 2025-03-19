import sys

import osc.commandline_git


class PullRequestGetCommand(osc.commandline_git.GitObsCommand):
    """
    Get details about the specified pull requests
    """

    name = "get"
    aliases = ["show"]  # for compatibility with osc
    parent = "PullRequestCommand"

    def init_arguments(self):
        from osc.commandline_git import complete_pr

        self.add_argument_owner_repo_pull(nargs="+").completer = complete_pr
        self.add_argument(
            "-p",
            "--patch",
            action="store_true",
            help="Show patches associated with the pull requests",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()

        num_entries = 0
        failed_entries = []
        for owner, repo, pull in args.owner_repo_pull:
            try:
                pr = gitea_api.PullRequest.get(self.gitea_conn, owner, repo, int(pull)).json()
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(f"{owner}/{repo}#{pull}")
                    continue
                raise
            print(gitea_api.PullRequest.to_human_readable_string(pr))

            if args.patch:
                print("")
                print(tty.colorize("Patch:", "bold"))
                patch = gitea_api.PullRequest.get_patch(self.gitea_conn, owner, repo, pull).data
                patch = highlight_diff(patch)
                print(patch.decode("utf-8"))

            print()

        print(f"Total entries: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(
                f"{tty.colorize('ERROR', 'red,bold')}: Couldn't retrieve the following pull requests: {', '.join(failed_entries)}",
                file=sys.stderr,
            )
            sys.exit(1)
