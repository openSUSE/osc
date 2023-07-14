import difflib

import osc.commandline
from .. import oscerr
from .._private.project import ProjectMeta
from ..core import raw_input


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
        meta = ProjectMeta.from_api(args.apiurl, args.project)
        old_meta = meta.to_string().splitlines()

        for repo in args.repo:
            meta.repository_remove(repo)
            meta.publish_remove_disable_repository(repo)

        new_meta = meta.to_string().splitlines()
        diff = difflib.unified_diff(old_meta, new_meta, fromfile="old", tofile="new")
        print("\n".join(diff))

        if not args.yes:
            print()
            print(f"You're changing meta of project '{args.project}'")
            reply = raw_input("Do you want to apply the changes? [y/N] ").lower()
            if reply != "y":
                raise oscerr.UserAbort()

        meta.to_api(args.apiurl, args.project)
