import argparse
import glob
import os
import subprocess
import sys

import osc.commandline_common
import osc.commands_git
from . import oscerr
from .output import print_msg


class OwnerRepoAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        from . import gitea_api

        try:
            if isinstance(value, list):
                namespace_value = [gitea_api.Repo.split_id(i) for i in value]
            else:
                namespace_value = gitea_api.Repo.split_id(value)
        except ValueError as e:
            raise argparse.ArgumentError(self, str(e))

        setattr(namespace, self.dest, namespace_value)


class OwnerRepoPullAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        from . import gitea_api

        try:
            if isinstance(value, list):
                namespace_value = [gitea_api.PullRequest.split_id(i) for i in value]
            else:
                namespace_value = gitea_api.PullRequest.split_id(value)
        except ValueError as e:
            raise argparse.ArgumentError(self, str(e))

        setattr(namespace, self.dest, namespace_value)


class BooleanAction(argparse.Action):
    def __call__(self, parser, namespace, value, option_string=None):
        if value is None:
            setattr(namespace, self.dest, None)
        elif value.lower() in ["0", "no", "false", "off"]:
            setattr(namespace, self.dest, False)
        elif value.lower() in ["1", "yes", "true", "on"]:
            setattr(namespace, self.dest, True)
        else:
            raise argparse.ArgumentError(self, f"Invalid boolean value: {value}")


class GitObsCommand(osc.commandline_common.Command):
    @property
    def gitea_conf(self):
        return self.main_command.gitea_conf

    @gitea_conf.setter
    def gitea_conf(self, value):
        self.main_command.gitea_conf = value

    @property
    def gitea_login(self):
        return self.main_command.gitea_login

    @gitea_login.setter
    def gitea_login(self, value):
        self.main_command.gitea_login = value

    @property
    def gitea_conn(self):
        return self.main_command.gitea_conn

    @gitea_conn.setter
    def gitea_conn(self, value):
        self.main_command.gitea_conn = value

    @property
    def quiet(self):
        if self.main_command._args.quiet:
            return True
        if self.gitea_login and self.gitea_login.quiet:
            return True
        return False

    def print_gitea_settings(self):
        if self.quiet:
            return
        print(f"Using the following Gitea settings:", file=sys.stderr)
        print(f" * Config path: {self.gitea_conf.path}", file=sys.stderr)
        print(f" * Login (name of the entry in the config file): {self.gitea_login.name}", file=sys.stderr)
        print(f" * URL: {self.gitea_login.url}", file=sys.stderr)
        print(f" * User: {self.gitea_login.user}", file=sys.stderr)
        print("", file=sys.stderr)

    def add_argument_owner_repo(self, **kwargs):
        dest = kwargs.pop("dest", "owner_repo")
        return self.add_argument(
            dest,
            action=OwnerRepoAction,
            help="Owner and repo: (format: <owner>/<repo>)",
            **kwargs,
        )

    def add_argument_owner_repo_pull(self, **kwargs):
        dest = kwargs.pop("dest", "owner_repo_pull")
        return self.add_argument(
            dest,
            action=OwnerRepoPullAction,
            help="Owner, repo and pull request number (format: <owner>/<repo>#<pull-request-number>)",
            **kwargs,
        )

    def add_argument_new_repo_name(self):
        return self.add_argument(
            "--new-repo-name",
            help="Name of the newly forked repo",
        )


def complete_login(prefix, parsed_args, **kwargs):
    from . import gitea_api

    conf = getattr(parsed_args, "gitea_config", None)
    gitea_conf = gitea_api.Config(conf)
    return [i.name for i in gitea_conf.list_logins()]


def complete_ssh_key_path(prefix, parsed_args, **kwargs):
    return glob.glob(os.path.expanduser("~/.ssh/*.pub"))


def complete_pr(prefix, parsed_args, **kwargs):
    from . import gitea_api

    conf = getattr(parsed_args, "gitea_config", None)
    login = getattr(parsed_args, "gitea_login", None)
    gitea_conf = gitea_api.Config(conf)
    gitea_login = gitea_conf.get_login(name=login)
    gitea_conn = gitea_api.Connection(gitea_login)
    pr_obj_list = gitea_api.PullRequest.search(
        gitea_conn,
        state="open",
    )
    pr_obj_list.sort()
    return [pr_obj.id for pr_obj in pr_obj_list]


def complete_checkout_pr(prefix, parsed_args, **kwargs):
    from . import gitea_api

    git = gitea_api.Git(".")
    owner, repo = git.get_owner_repo()

    conf = getattr(parsed_args, "gitea_config", None)
    login = getattr(parsed_args, "gitea_login", None)
    gitea_conf = gitea_api.Config(conf)
    gitea_login = gitea_conf.get_login(name=login)
    gitea_conn = gitea_api.Connection(gitea_login)
    pr_obj_list = gitea_api.PullRequest.list(
        gitea_conn,
        owner=owner,
        repo=repo,
        state="open",
    )
    pr_obj_list.sort()
    return [str(pr_obj.number) for pr_obj in pr_obj_list]


class GitObsMainCommand(osc.commandline_common.MainCommand):
    """
    git-obs is a command-line client for interacting with Git repositories within a Gitea instance that is part of an Open Build Service (OBS).
    """

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
            "-q",
            "--quiet",
            action="store_true",
            help="Mute unnecessary output",
        )

        self.add_argument(
            "--gitea-config",
            help="Path to gitea config. Default: $GIT_OBS_CONFIG or ~/.config/tea/config.yml.",
        )

        self.add_argument(
            "-G",
            "--gitea-login",
            help=(
                "Name of the login entry in the config file. Default: $GIT_OBS_LOGIN or the default entry from the config file.\n"
                "Alternatively, you can use gitea url as long as there's only a single matching entry in the config file.\n"
                "\n"
                "You can omit this argument and set GIT_OBS_GITEA_URL, GIT_OBS_GITEA_USER, and GIT_OBS_GITEA_TOKEN environmental variables instead.\n"
                "Optional variables: GIT_OBS_GITEA_SSH_KEY\n"
                "\n"
                "To override the existing values from the config file, you can specify the following environmental variables:\n"
                " - GIT_OBS_LOGIN_<LOGIN-NAME>_USER\n"
                " - GIT_OBS_LOGIN_<LOGIN-NAME>_TOKEN\n"
                " - GIT_OBS_LOGIN_<LOGIN-NAME>_SSH_KEY\n"
                "Setting new ``name`` or ``url`` is not possible.\n"
                "Please note that the login name that is part of the environmental variable name is case sensitive."
            ),
        ).completer = complete_login

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
    def main(cls, argv=None, run=True, argparse_manpage=False):
        """
        Initialize OscMainCommand, load all commands and run the selected command.
        """
        cmd = cls()
        # argparse-manpage splits command's help text to help and description
        # we normally use both in the --help output, but want to change that for argparse-manpage
        cmd.argparse_manpage = argparse_manpage
        cmd.load_commands()
        cmd.enable_autocomplete()
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

    @gitea_conf.setter
    def gitea_conf(self, value):
        self._gitea_conf = value

    @property
    def gitea_login(self):
        from . import gitea_api

        if self._gitea_login is None:
            try:
                self._gitea_login = self.gitea_conf.get_login(name=self._args.gitea_login)
            except gitea_api.Login.DoesNotExist as e:
                try:
                    self._gitea_login = self.gitea_conf.get_login_by_url_user(url=self._args.gitea_login)
                except gitea_api.Login.DoesNotExist:
                    raise e

        return self._gitea_login

    @gitea_login.setter
    def gitea_login(self, value):
        self._gitea_login = value

    @property
    def gitea_conn(self):
        from . import gitea_api

        if self._gitea_conn is None:
            self._gitea_conn = gitea_api.Connection(self.gitea_login)
            assert self._gitea_login is not None
        return self._gitea_conn

    @gitea_conn.setter
    def gitea_conn(self, value):
        self._gitea_conn = value


def argparse_manpage_get_parser():
    """
    Needed by argparse-manpage to generate man pages from the argument parser.
    """
    main, _ = GitObsMainCommand.main(run=False, argparse_manpage=True)
    return main.parser


def main():
    try:
        GitObsMainCommand.main()
    except KeyboardInterrupt:
        print_msg("Interrupted on user request", print_to="error")
        sys.exit(130)
    except oscerr.OscBaseError as e:
        print_msg(str(e), print_to="error")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print_msg(str(e), print_to="error")
        sys.exit(1)

if __name__ == "__main__":
    main()
