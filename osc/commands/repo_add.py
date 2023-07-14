import difflib

import osc.commandline
from .. import oscerr
from .._private.project import ProjectMeta
from ..core import raw_input


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
        paths = []
        for path in args.paths:
            if "/" not in path:
                self.parser.error(f"Invalid path (expected format is PROJECT/REPO): {path}")
            project, repo = path.split("/")
            paths.append({"project": project, "repository": repo})

        meta = ProjectMeta.from_api(args.apiurl, args.project)
        old_meta = meta.to_string().splitlines()

        meta.repository_add(args.repo, args.arches, paths)
        if args.disable_publish:
            meta.publish_add_disable_repository(args.repo)

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
