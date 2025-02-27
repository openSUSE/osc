import sys
import urllib.parse

import osc.commandline
import osc.commandline_git


class ForkCommand(osc.commandline.OscCommand):
    """
    Fork a package with sources managed in Gitea
    """

    name = "fork"

    # inject some git-obs methods to avoid duplicating code
    add_argument_new_repo_name = osc.commandline_git.GitObsCommand.add_argument_new_repo_name
    post_parse_args = osc.commandline_git.GitObsMainCommand.post_parse_args
    print_gitea_settings = osc.commandline_git.GitObsCommand.print_gitea_settings

    def init_arguments(self):
        # inherit global options from the main git-obs command
        osc.commandline_git.GitObsMainCommand.init_arguments(self)

        self.add_argument(
            "project",
            help="Name of the project",
        )

        self.add_argument(
            "package",
            help="Name of the package",
        )

        self.add_argument_new_repo_name()

    def run(self, args):
        from osc import conf as osc_conf
        from osc import gitea_api
        from osc import obs_api
        from osc.output import tty

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

        # find a credentials entry for url and OBS user (there can be multiple users configured for a single URL in the config file)
        gitea_conf = gitea_api.Config(args.gitea_config)
        gitea_login = gitea_conf.get_login_by_url_user(url=url, user=osc_conf.get_apiurl_usr(args.apiurl))
        gitea_conn = gitea_api.Connection(gitea_login)

        self.print_gitea_settings()
        print(f"Forking git repo {owner}/{repo} ...", file=sys.stderr)

        # the branch was not specified, fetch the default branch from the repo
        if branch:
            fork_branch = branch
        else:
            repo_data = gitea_api.Repo.get(gitea_conn, owner, repo).json()
            branch = repo_data["default_branch"]
            fork_branch = branch

        # check if the scmsync branch exists in the source repo
        parent_branch_data = gitea_api.Branch.get(gitea_conn, owner, repo, fork_branch).json()

        try:
            repo_data = gitea_api.Fork.create(gitea_conn, owner, repo, new_repo_name=args.new_repo_name).json()
            fork_owner = repo_data["owner"]["login"]
            fork_repo = repo_data["name"]
            print(f" * Fork created: {fork_owner}/{fork_repo}")
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print(f" * Fork already exists: {fork_owner}/{fork_repo}")

        # XXX: implicit branch name should be forbidden; assumptions are bad
        fork_scmsync = urllib.parse.urlunparse(
            (parsed_scmsync_url.scheme, parsed_scmsync_url.netloc, f"{fork_owner}/{fork_repo}", "", "", fork_branch)
        )

        print()
        print(f"Forking OBS package {args.project}/{args.package} ...")
        print(f" * OBS apiurl: {args.apiurl}")
        status = obs_api.Package.cmd_fork(args.apiurl, args.project, args.package, scmsync=fork_scmsync)
        target_project = status.data["targetproject"]
        target_package = status.data["targetpackage"]
        # XXX: the current OBS API is not ideal; we don't get any info whether the new package exists already; 404 would be probably nicer
        print(f" * Fork created: {target_project}/{target_package}")
        print(f" * scmsync URL: {fork_scmsync}")

        # check if the scmsync branch exists in the forked repo
        fork_branch_data = gitea_api.Branch.get(gitea_conn, fork_owner, fork_repo, fork_branch).json()

        parent_commit = parent_branch_data["commit"]["id"]
        fork_commit = fork_branch_data["commit"]["id"]
        if parent_commit != fork_commit:
            print()
            print(f"{tty.colorize('ERROR', 'red,bold')}: The branch in the forked repo is out of sync with the parent")
            print(f" * Fork: {fork_owner}/{fork_repo}#{fork_branch}, commit: {fork_commit}")
            print(f" * Parent: {owner}/{repo}#{fork_branch}, commit: {parent_commit}")
            print(" * If this is not intentional, please clone the fork and fix the branch manually")
            sys.exit(1)
