import osc.commandline_git


class MetaPullCommand(osc.commandline_git.GitObsCommand):
    """
    Pull metadata about the project or package from Gitea.
    """

    name = "pull"
    parent = "MetaCommand"

    def init_arguments(self):
        pass

    def run(self, args):
        from osc import gitea_api
        from osc.git_scm.configuration import Configuration
        from osc.git_scm.manifest import Manifest
        from osc.git_scm.store import LocalGitStore
        from osc.output import KeyValueTable

        self.print_gitea_settings()

        store = LocalGitStore(".")

        apiurl = None
        project = None

        # read apiurl and project from _manifest that lives in <owner>/_ObsPrj, matching <branch>
        # XXX: when the target branch doesn't exist, file from the default branch is returned
        if store.is_package:
            try:
                owner, _ = store._git.get_owner_repo()
                repo = "_ObsPrj"
                branch = store._git.current_branch

                url = self.gitea_conn.makeurl("repos", owner, repo, "raw", "_manifest", query={"ref": branch})
                response = self.gitea_conn.request("GET", url)
                if response.data:
                    manifest = Manifest.from_string(response.data.decode("utf-8"))
                    if manifest.obs_apiurl:
                        apiurl = manifest.obs_apiurl
                    if manifest.obs_project:
                        project = manifest.obs_project
            except gitea_api.GiteaException as e:
                if e.status != 404:
                    raise

        # read apiurl from the global configuration in obs/configuration. branch
        if not apiurl:
            try:
                url = self.gitea_conn.makeurl("repos", "obs", "configuration", "raw", "configuration.yaml", query={"ref": "main"})
                response = self.gitea_conn.request("GET", url)
                if response.data:
                    configuration = Configuration.from_string(response.data.decode("utf-8"))
                    if configuration.obs_apiurl:
                        apiurl = configuration.obs_apiurl
            except gitea_api.GiteaException as e:
                if e.status != 404:
                    raise

        if apiurl:
            store.apiurl = apiurl

        if project:
            store.project = project

        branch = store._git.current_branch
        meta = store._read_meta(branch=branch).dict()
        meta.pop("header", None)

        table = KeyValueTable(min_key_length=10)
        table.add("Branch", branch, color="bold")
        for key, value in meta.items():
            table.add(key, value)
        print(str(table))
