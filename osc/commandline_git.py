import os
import sys

import osc.commandline_common
import osc.commands_git
from . import oscerr
from .output import print_msg


class GitObsCommand(osc.commandline_common.Command):
    @property
    def gitea_conf(self):
        return self.main_command.gitea_conf

    @property
    def gitea_login(self):
        return self.main_command.gitea_login

    @property
    def gitea_conn(self):
        return self.main_command.gitea_conn

    def print_gitea_settings(self):
        print(f"Using the following Gitea settings:", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print(f" * Login (name of the entry in the config file): {self.gitea_login.name}", file=sys.stderr)
        print(f" * URL: {self.gitea_login.url}", file=sys.stderr)
        print(f" * User: {self.gitea_login.user}", file=sys.stderr)
        print("", file=sys.stderr)

    def add_argument_owner(self):
        self.add_argument(
            "owner",
            help="Name of the repository owner (login, org)",
        )

    def add_argument_repo(self):
        self.add_argument(
            "repo",
            help="Name of the repository",
        )

    def add_argument_new_repo_name(self):
        self.add_argument(
            "--new-repo-name",
            help="Name of the newly forked repo",
        )


class GitObsMainCommand(osc.commandline_common.MainCommand):
    name = "git-obs"

    MODULES = (
        ("osc.commands_git", osc.commands_git.__path__[0]),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._args = None
        self._gitea_conf = None
        self._gitea_login = None
        self._gitea_conn = None

    def init_arguments(self):
        self.add_argument(
            "--gitea-config",
            help="Path to gitea config. Default: $GIT_OBS_CONFIG or ~/.config/tea/config.yml.",
        )

        self.add_argument(
            "-G",
            "--gitea-login",
            help="Name of the login entry in the config file. Default: $GIT_OBS_LOGIN or the default entry from the config file.",
        )

    def post_parse_args(self, args):
        if not args.gitea_config:
            value = os.getenv("GIT_OBS_CONFIG", "").strip()
            if value:
                args.gitea_config = value

        if not args.gitea_login:
            value = os.getenv("GIT_OBS_LOGIN", "").strip()
            if value:
                args.gitea_login = value

        self._args = args


    @classmethod
    def main(cls, argv=None, run=True):
        """
        Initialize OscMainCommand, load all commands and run the selected command.
        """
        cmd = cls()
        cmd.load_commands()
        if run:
            args = cmd.parse_args(args=argv)
            exit_code = cmd.run(args)
            sys.exit(exit_code)
        else:
            args = None
        return cmd, args

    @property
    def gitea_conf(self):
        from . import gitea_api

        if self._gitea_conf is None:
            self._gitea_conf = gitea_api.Config(self._args.gitea_config)
        return self._gitea_conf

    @property
    def gitea_login(self):
        if self._gitea_login is None:
            self._gitea_login = self.gitea_conf.get_login(name=self._args.gitea_login)
        return self._gitea_login

    @property
    def gitea_conn(self):
        from . import gitea_api

        if self._gitea_conn is None:
            self._gitea_conn = gitea_api.Connection(self.gitea_login)
            assert self._gitea_login is not None
        return self._gitea_conn


def main():
    try:
        GitObsMainCommand.main()
    except oscerr.OscBaseError as e:
        print_msg(str(e), print_to="error")
        sys.exit(1)


if __name__ == "__main__":
    main()
