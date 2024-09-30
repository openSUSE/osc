import osc.commandline


class ForkCommand(osc.commandline.OscCommand):
    """
    Fork a package that is managed in Git
    """

    name = "fork"

    def init_arguments(self):
        self.add_argument(
            "project",
            help="Name of the project",
        )

        self.add_argument(
            "package",
            help="Name of the package",
        )

    def run(self, args):
        import urllib.parse
        from osc import conf as osc_conf
        from osc import gitea_api
        from osc import obs_api
        from osc.output import print_msg

        auth_token = osc_conf.config.api_host_options[args.apiurl].get("gitea_auth_token", None)
        if not auth_token:
            raise RuntimeError(f"Option 'gitea_auth_token' is not configured for apiurl '{args.apiurl}'")

        package = obs_api.Package.from_api(args.apiurl, args.project, args.package)
        if not package.scmsync:
            raise RuntimeError("Forking is possibly only with packages managed in Git (the <scmsync> element must be set in the package meta)")

        parsed_scmsync_url = urllib.parse.urlparse(package.scmsync, scheme="https")

        url = urllib.parse.urlunparse((parsed_scmsync_url.scheme, parsed_scmsync_url.netloc, "", "", "", ""))
        owner, repo = parsed_scmsync_url.path.strip("/").split("/")
        branch = parsed_scmsync_url.fragment or None

        gitea = gitea_api.GiteaConnection(url, auth_token=auth_token)

        try:
            _, reply = gitea.fork(owner, repo)
            fork_owner = reply["owner"]["name"]
            fork_repo = reply["name"]
        except gitea_api.GiteaForkExists as e:
            fork_owner = e.owner
            fork_repo = e.repo
            print_msg(f"Re-using an existing fork: {fork_owner}/{fork_repo}", print_to="debug")

        # TODO: branch package if `branch` is set?
        #       or just print a message?
        #       if the package was forked a long time ago, the branches might be outdated and we need the user to set a remote and branch the right contents

        # TODO: use urlunparse()
        scmsync = f"{url}/{fork_owner}/{fork_repo}"
        if branch:
            scmsync += "#" + branch

        obs_api.Package.cmd_fork(args.apiurl, args.project, args.package, scmsync=scmsync)
