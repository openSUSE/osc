import sys

import osc.commandline_git


class RepoForkCommand(osc.commandline_git.GitObsCommand):
    """
    Fork a git repo
    """

    name = "fork"
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument_owner_repo(nargs="+")
        self.add_argument_new_repo_name()

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        self.print_gitea_settings()

        if len(args.owner_repo) > 1 and args.new_repo_name:
            self.parser.error("The --new-repo-name option cannot be used with multiple repos")

        num_entries = 0
        failed_entries = []
        for owner, repo in args.owner_repo:
            print(f"Forking git repo {owner}/{repo} ...", file=sys.stderr)
            try:
                response = gitea_api.Fork.create(self.gitea_conn, owner, repo, new_repo_name=args.new_repo_name)
                repo = response.json()
                fork_owner = repo["owner"]["login"]
                fork_repo = repo["name"]
                print(f" * Fork created: {fork_owner}/{fork_repo}", file=sys.stderr)
                num_entries += 1
            except gitea_api.ForkExists as e:
                fork_owner = e.fork_owner
                fork_repo = e.fork_repo
                print(f" * Fork already exists: {fork_owner}/{fork_repo}", file=sys.stderr)
                print(f" * {tty.colorize('WARNING', 'yellow,bold')}: Using an existing fork with a different name than requested", file=sys.stderr)
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    print(f" * {tty.colorize('ERROR', 'red,bold')}: Repo doesn't exist: {owner}/{repo}", file=sys.stderr)
                    failed_entries.append(f"{owner}/{repo}")
                    continue
                raise

        print("", file=sys.stderr)
        print(f"Total forked repos: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Couldn't fork the following repos: {', '.join(failed_entries)}", file=sys.stderr)
            sys.exit(1)
