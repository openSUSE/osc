import osc.commandline_git


class MetaFooCommand(osc.commandline_git.GitObsCommand):
    """
    Reset metadata in store
    """

    name = "reset"
    parent = "MetaCommand"

    def init_arguments(self):
        self.add_argument(
            "--branch",
            help="Manage values for the specified branch (default: current branch)",
        )

    def run(self, args):
        from osc.git_scm.store import LocalGitStore

        store = LocalGitStore(".")
        branch = args.branch or store._git.current_branch
        print(f"Resetting meta for branch '{branch}' ...")
        store.reset(branch=branch)
