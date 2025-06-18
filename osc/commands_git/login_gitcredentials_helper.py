import osc.commandline_git


class LoginGitcredentialsHelperCommand(osc.commandline_git.GitObsCommand):
    """
    A gitcredentials helper

    To use token auth for git operations, switch git from using SSH to http(s):
        git-obs login update <login> --new-git-uses-http=1

    and add the following entry to .gitconfig:
        [credential "https://src.example.com"]
            helper = "git-obs -G <login> login gitcredentials-helper"
    """

    name = "gitcredentials-helper"
    parent = "LoginCommand"
    hidden = True

    def init_arguments(self):
        self.parser.add_argument(
            "operation",
            # see gitcredentials(7) for more details
            choices=["get", "store", "erase"],
        )

    def run(self, args):
        import shlex

        if args.operation == "get":
            print(f"username={shlex.quote(self.gitea_login.user)}")
            print(f"password={shlex.quote(self.gitea_login.token)}")
