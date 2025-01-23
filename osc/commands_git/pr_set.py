import sys

import osc.commandline_git


def b(value: str):
    if value is not None:
        return value.lower() in ["1", "yes", "true", "on"]
    return None


class PullRequestSetCommand(osc.commandline_git.GitObsCommand):
    """
    Change a pull request
    """

    name = "set"
    parent = "PullRequestCommand"

    def init_arguments(self):
        self.add_argument_owner_repo_pull(nargs="+")
        self.add_argument(
            "--title",
        )
        self.add_argument(
            "--description",
        )
        self.add_argument(
            "--allow-maintainer-edit",
            action=osc.commandline_git.BooleanAction,
            help="Users with write access to the base branch can also push to the pull request's head branch",
        )

    def run(self, args):
        from osc import gitea_api
        from osc.core import highlight_diff
        from osc.output import tty

        self.print_gitea_settings()
        print(args)

        num_entries = 0
        failed_entries = []
        for owner, repo, pull in args.owner_repo_pull:
            try:
                pr = gitea_api.PullRequest.set(
                    self.gitea_conn,
                    owner,
                    repo,
                    int(pull),
                    title=args.title,
                    description=args.description,
                    allow_maintainer_edit=args.allow_maintainer_edit,
                ).json()
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    failed_entries.append(f"{owner}/{repo}#{pull}")
                    continue
                raise

            print(gitea_api.PullRequest.to_human_readable_string(pr))
            print()

        print(f"Total modified entries: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(
                f"{tty.colorize('ERROR', 'red,bold')}: Couldn't change the following pull requests: {', '.join(failed_entries)}",
                file=sys.stderr,
            )
            sys.exit(1)
