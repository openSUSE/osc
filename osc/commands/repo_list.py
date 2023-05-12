import osc.commandline
from .._private.project import ProjectMeta


class RepoListCommand(osc.commandline.OscCommand):
    """
    List repositories in project meta
    """

    name = "list"
    aliases = ["ls"]
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument(
            "project",
            help="Name of the project",
        )

    def run(self, args):
        meta = ProjectMeta.from_api(args.apiurl, args.project)
        for repo in meta.repository_list():
            print(f"Repository: {repo['name']}")
            print("Architectures:")
            for arch in repo["archs"]:
                print(f"    {arch}")
            print("Paths:")
            for path in repo["paths"]:
                print(f"    {path['project']}/{path['repository']}")
            print()
