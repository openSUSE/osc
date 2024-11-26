import difflib

import osc.commandline
from .. import oscerr


class RepoAddCommand(osc.commandline.OscCommand):
    """
    Add a repository to project meta
    """

    name = "add"
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument(
            "project",
            help="Name of the project",
        )
        self.add_argument(
            "--repo",
            metavar="NAME",
            required=True,
            help="Name of the repository we're adding",
        )
        self.add_argument(
            "--arch",
            dest="arches",
            metavar="[ARCH]",
            action="append",
            required=True,
            help="Architecture of the repository. Can be specified multiple times.",
        )
        self.add_argument(
            "--path",
            dest="paths",
            metavar="[PROJECT/REPO]",
            action="append",
            required=True,
            help="Path associated to the repository. Format is PROJECT/REPO. Can be specified multiple times.",
        )
        self.add_argument(
            "--disable-publish",
            action="store_true",
            default=False,
            help="Disable publishing the added repository",
        )
        self.add_argument(
            "--yes",
            action="store_true",
            help="Proceed without asking",
        )

    def run(self, args):
        from .. import obs_api
        from ..output import get_user_input

        paths = []
        for path in args.paths:
            if "/" not in path:
                self.parser.error(f"Invalid path (expected format is PROJECT/REPO): {path}")
            project, repo = path.split("/")
            paths.append({"project": project, "repository": repo})

        project_obj = obs_api.Project.from_api(args.apiurl, args.project)
        old = project_obj.to_string()

        matching_repos = [i for i in project_obj.repository_list or [] if i.name == args.repo]
        if matching_repos:
            raise oscerr.OscValueError(f"Repository '{args.repo}' already exists in project meta")

        project_obj.repository_list.append(
            {
                "name": args.repo,
                "arch_list": args.arches,
                "path_list": paths,
            }
        )

        if args.disable_publish:
            matching_publish_disable_repos = [
                i for i in project_obj.publish_list or [] if i.flag == "disable" and i.repository == args.repo
            ]
            if not matching_publish_disable_repos:
                if project_obj.publish_list is None:
                    project_obj.publish_list = []
                project_obj.publish_list.append(
                    {
                        "flag": "disable",
                        "repository": args.repo,
                    }
                )

        if not args.yes:
            new = project_obj.to_string()
            diff = difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile="old", tofile="new")
            print("\n".join(diff))
            print()

            reply = get_user_input(
                f"""
                You're changing meta of project '{args.project}'
                Do you want to apply the changes?
                """,
                answers={"y": "yes", "n": "no"},
            )

            if reply == "n":
                raise oscerr.UserAbort()

        project_obj.to_api(args.apiurl)
