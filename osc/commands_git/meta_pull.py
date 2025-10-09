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
        from osc.git_scm.store import GitStore
        from osc.output import KeyValueTable

        self.print_gitea_settings()

        store = GitStore(".", check=False)
        branch = store._git.current_branch
        changed = store.pull(self.gitea_conn)

        table = KeyValueTable(min_key_length=10)
        table.add("Branch", branch, color="bold")
        for key, value in changed.items():
            table.add(key, value)
        print(str(table))
