import osc.commandline
from ..output import KeyValueTable
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
        table = KeyValueTable()
        for repo in meta.repository_list():
            table.add("Repository", repo["name"], color="bold")
            table.add("Architectures", ", ".join(repo["archs"]))
            if repo["paths"]:
                paths = [f"{path['project']}/{path['repository']}" for path in repo["paths"]]
                table.add("Paths", paths)
            table.newline()
        print(str(table))
