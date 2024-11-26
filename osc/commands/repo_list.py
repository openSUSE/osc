import osc.commandline


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
        from .. import obs_api
        from ..output import KeyValueTable

        project_obj = obs_api.Project.from_api(args.apiurl, args.project)
        repo_flags = project_obj.resolve_repository_flags()

        flag_map = {}
        for (repo_name, arch), data in repo_flags.items():
            for flag_name, flag_value in data.items():
                if flag_value is None:
                    continue
                action = "enable" if flag_value else "disable"
                flag_map.setdefault(repo_name, {}).setdefault(flag_name, {}).setdefault(action, []).append(arch)

        table = KeyValueTable()
        for repo in project_obj.repository_list or []:
            table.add("Repository", repo.name, color="bold")
            table.add("Architectures", ", ".join(repo.arch_list))
            if repo.path_list:
                paths = [f"{path.project}/{path.repository}" for path in repo.path_list]
                table.add("Paths", paths)

            if repo.name in flag_map:
                table.add("Flags", None)
                for flag_name in flag_map[repo.name]:
                    lines = []
                    for action, archs in flag_map[repo.name][flag_name].items():
                        lines.append(f"{action + ':':<8s} {', '.join(archs)}")
                    lines.sort()
                    table.add(flag_name, lines, indent=4)

            table.newline()
        print(str(table))
