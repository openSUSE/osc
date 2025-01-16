import subprocess
import sys

import osc.commandline_git


class RepoCloneCommand(osc.commandline_git.GitObsCommand):
    """
    Clone a git repo

    NOTE: Some of the options may result in setting "core.sshCommand"
    config option in the git repository."
    """

    name = "clone"
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument_owner_repo(nargs="+")

        self.add_argument(
            "-a",
            "--anonymous",
            action="store_true",
            default=None,
            help="Clone anonymously via the http protocol",
        )

        self.add_argument(
            "-i",
            "--ssh-key",
            help="Path to a private SSH key (identity file)",
        )

        self.add_argument(
            "--no-ssh-strict-host-key-checking",
            action="store_true",
            help="Set 'StrictHostKeyChecking no' ssh option",
        )

        # TODO: replace with an optional argument to get closer to the `git clone` command?
        self.add_argument(
            "--directory",
            help="Clone into the given directory",
        )

    def run(self, args):
        from osc import gitea_api

        from osc.output import tty

        self.print_gitea_settings()

        if len(args.owner_repo) > 1 and args.directory:
            self.parser.error("The --directory option cannot be used with multiple repos")

        num_entries = 0
        failed_entries = []
        for owner, repo in args.owner_repo:
            print(f"Cloning git repo {owner}/{repo} ...", file=sys.stderr)
            try:
                gitea_api.Repo.clone(
                    self.gitea_conn,
                    owner,
                    repo,
                    directory=args.directory,
                    anonymous=args.anonymous,
                    add_remotes=True,
                    ssh_private_key_path=args.ssh_key or self.gitea_login.ssh_key,
                    ssh_strict_host_key_checking=not(args.no_ssh_strict_host_key_checking),
                )
                num_entries += 1
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    print(f" * {tty.colorize('ERROR', 'red,bold')}: Repo doesn't exist: {owner}/{repo}", file=sys.stderr)
                    failed_entries.append(f"{owner}/{repo}")
                    continue
                raise
            except subprocess.CalledProcessError as e:
                print(f" * {tty.colorize('ERROR', 'red,bold')}: git clone failed", file=sys.stderr)
                failed_entries.append(f"{owner}/{repo}")
                continue

        print("", file=sys.stderr)
        print(f"Total cloned repos: {num_entries}", file=sys.stderr)
        if failed_entries:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Couldn't clone the following repos: {', '.join(failed_entries)}", file=sys.stderr)
            sys.exit(1)
