import osc.commandline

from . import common


class ForkObsPackageCommand(osc.commandline.OscCommand):
    """
    Fork an OBS package that is managed in Git
    """

    name = "fork-obs-package"

    def init_arguments(self):
        common.cmd_add_apiurl(self)
        common.cmd_add_project(self)
        common.cmd_add_package(self)
        common.cmd_add_new_repo_name(self)

    def run(self, args):
        import sys
        import urllib.parse
        from osc import conf as osc_conf
        from osc import gitea_api
        from osc import obs_api
        from osc.output import print_msg

        osc_conf.get_config(override_apiurl=args.apiurl)
        args.apiurl = osc_conf.config.apiurl

        # get the package meta from the OBS API first
        package = obs_api.Package.from_api(args.apiurl, args.project, args.package)
        if not package.scmsync:
            raise RuntimeError(
                "Forking is possible only with packages managed in Git (the <scmsync> element must be set in the package meta)"
            )

        # parse gitea url, owner, repo and branch from the scmsync url
        parsed_scmsync_url = urllib.parse.urlparse(package.scmsync, scheme="https")
        url = urllib.parse.urlunparse((parsed_scmsync_url.scheme, parsed_scmsync_url.netloc, "", "", "", ""))
        owner, repo = parsed_scmsync_url.path.strip("/").split("/")
        branch = parsed_scmsync_url.fragment or None

        conf = gitea_api.Config()
        # find a credentials entry for url and OBS user (there can be multiple users configured for a single URL in the config file)
        login = conf.get_login_by_url_user(url=url, user=osc_conf.get_apiurl_usr(args.apiurl))
        conn = gitea_api.Connection(login)

        print_msg(f"Forking git repo {owner}/{repo} ...", print_to="stderr")
        print_msg(f" * URL: {login.url}", print_to="stderr")
        print_msg(f" * User: {login.user}", print_to="stderr")

        # the branch was not specified, fetch the default branch from the repo
        if branch:
            fork_branch = branch
        else:
            response = gitea_api.get_repo(conn, owner, repo)
            repo = response.json()
            branch = repo["default_branch"]
            fork_branch = branch

        # check if the scmsync branch exists in the source repo
        parent_branch_data = gitea_api.get_branch(conn, owner, repo, fork_branch).json()

        try:
            response = gitea_api.fork_repo(conn, owner, repo, new_repo_name=args.new_repo_name)
            repo = response.json()
            fork_owner = repo["owner"]["login"]
            fork_repo = repo["name"]
            print_msg(f" * Fork created: {fork_owner}/{fork_repo}", print_to="stderr")
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print_msg(f" * Fork already exists: {fork_owner}/{fork_repo}", print_to="stderr")

        # XXX: implicit branch name should be forbidden; assumptions are bad
        fork_scmsync = urllib.parse.urlunparse(
            (parsed_scmsync_url.scheme, parsed_scmsync_url.netloc, f"{fork_owner}/{fork_repo}", "", "", fork_branch)
        )

        print_msg(f"Forking OBS package {args.project}/{args.package} ...", print_to="stderr")
        print_msg(f" * OBS apiurl: {args.apiurl}", print_to="stderr")
        status = obs_api.Package.cmd_fork(args.apiurl, args.project, args.package, scmsync=fork_scmsync)
        target_project = status.data["targetproject"]
        target_package = status.data["targetpackage"]
        # XXX: the current OBS API is not ideal; we don't get any info whether the new package exists already; 404 would be probably nicer
        print_msg(f" * Fork created: {target_project}/{target_package}", print_to="stderr")
        print_msg(f" * scmsync URL: {fork_scmsync}", print_to="stderr")

        # check if the scmsync branch exists in the forked repo
        fork_branch_data = gitea_api.get_branch(conn, fork_owner, fork_repo, fork_branch).json()

        parent_commit = parent_branch_data["commit"]["id"]
        fork_commit = fork_branch_data["commit"]["id"]
        if parent_commit != fork_commit:
            print_msg(f"The branch in the forked repo is out of sync with the parent", print_to="error")
            print_msg(f" * Fork: {fork_owner}/{fork_repo}#{fork_branch}, commit: {fork_commit}", print_to="error")
            print_msg(f" * Parent: {owner}/{repo}#{fork_branch}, commit: {parent_commit}", print_to="error")
            print_msg(" * If this is not intentional, please clone the fork and fix the branch manually", print_to="error")
            sys.exit(1)
