import difflib

import osc.commandline
from .. import oscerr


class RepoRemoveCommand(osc.commandline.OscCommand):
    """
    Remove repositories from project meta
    """

    name = "remove"
    aliases = ["rm"]
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument(
            "project",
            help="Name of the project",
        )
        self.add_argument(
            "--repo",
            metavar="[NAME]",
            action="append",
            required=True,
            help="Name of the repository we're removing. Can be specified multiple times.",
        )
        self.add_argument(
            "--yes",
            action="store_true",
            help="Proceed without asking",
        )

    def run(self, args):
        from .. import obs_api
        from ..output import get_user_input

        project_obj = obs_api.Project.from_api(args.apiurl, args.project)
        old = project_obj.to_string()

        for repo in args.repo:
            if project_obj.repository_list is not None:
                project_obj.repository_list = [i for i in project_obj.repository_list if i.name != repo]
            if project_obj.publish_list is not None:
                project_obj.publish_list = [
                    i for i in project_obj.publish_list if i.flag != "disable" or i.repository != repo
                ]

        if not project_obj.has_changed():
            return

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
