import osc.commandline_git


class RepoCloneCommand(osc.commandline_git.GitObsCommand):
    """
    Clone a git repo
    """

    name = "clone"
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument_owner()
        self.add_argument_repo()

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

        self.print_gitea_settings()

        gitea_api.Repo.clone(
            self.gitea_conn,
            args.owner,
            args.repo,
            directory=args.directory,
            anonymous=args.anonymous,
            add_remotes=True,
            ssh_private_key_path=self.gitea_login.ssh_key or args.ssh_key,
            ssh_strict_host_key_checking=not(args.no_ssh_strict_host_key_checking),
        )
