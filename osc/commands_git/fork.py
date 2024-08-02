import osc.commandline

from . import common


# TODO: move 'fork' and 'clone' commands under 'repo' command?


class ForkCommand(osc.commandline.OscCommand):
    """
    Fork a package that is managed in Git
    """

    name = "fork"

    def init_arguments(self):
        common.cmd_add_login(self)
        common.cmd_add_owner(self)
        common.cmd_add_repo(self)
        common.cmd_add_new_repo_name(self)

    def run(self, args):
        import urllib.parse
        from osc import conf as osc_conf
        from osc import gitea_api
        from osc.output import print_msg

        conf = gitea_api.Config()
        login = conf.get_login(args.gitea_login_name)

        print_msg(f"Forking git repo {args.owner}/{args.repo} ...", print_to="stderr")
        print_msg(f" * URL: {login.url}", print_to="stderr")
        print_msg(f" * User: {login.user}", print_to="stderr")

        conn = gitea_api.Connection(login)

        try:
            response = gitea_api.fork_repo(conn, args.owner, args.repo, new_repo_name=args.new_repo_name)
            repo = response.json()
            fork_owner = repo["owner"]["login"]
            fork_repo = repo["name"]
            print_msg(f" * Fork created: {fork_owner}/{fork_repo}", print_to="stderr")
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print_msg(f" * Fork already exists: {fork_owner}/{fork_repo}", print_to="stderr")
