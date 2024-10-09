import sys

import osc.commandline_git


# TODO: move 'fork' and 'clone' commands under 'repo' command?


class ForkCommand(osc.commandline_git.GitObsCommand):
    """
    Fork a package that is managed in Git
    """

    name = "fork"

    def init_arguments(self):
        self.add_argument_owner()
        self.add_argument_repo()
        self.add_argument_new_repo_name()

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        self.print_gitea_settings()

        print(f"Forking git repo {args.owner}/{args.repo} ...", file=sys.stderr)
        try:
            response = gitea_api.Fork.create(self.gitea_conn, args.owner, args.repo, new_repo_name=args.new_repo_name)
            repo = response.json()
            fork_owner = repo["owner"]["login"]
            fork_repo = repo["name"]
            print(f" * Fork created: {fork_owner}/{fork_repo}", file=sys.stderr)
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print(f" * Fork already exists: {fork_owner}/{fork_repo}", file=sys.stderr)
            print(f" * {tty.colorize('WARNING', 'yellow,bold')}: Using an existing fork with a different name than requested", file=sys.stderr)
