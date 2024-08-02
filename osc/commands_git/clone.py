import osc.commandline

from . import common


class CloneCommand(osc.commandline.OscCommand):
    """
    Clone a project or a package
    """

    name = "clone"

    def init_arguments(self):
        common.cmd_add_login(self)
        common.cmd_add_owner(self)
        common.cmd_add_repo(self)

        self.add_argument(
            "-a",
            "--anonymous",
            action="store_true",
            default=None,
            help="Clone anonymously via the http protocol",
        )

        self.add_argument(
            "--directory",
            help="Clone into the given directory",
        )

    def run(self, args):
        from osc import gitea_api

        conf = gitea_api.Config()
        login = conf.get_login(name=args.gitea_login_name)
        conn = gitea_api.Connection(login)
        gitea_api.clone_repo(
            conn,
            args.owner,
            args.repo,
            directory=args.directory,
            anonymous=args.anonymous,
            add_remotes=True,
        )
