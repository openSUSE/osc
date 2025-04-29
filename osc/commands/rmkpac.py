import sys
from urllib.error import HTTPError

import osc.commandline


class RmkpacCommand(osc.commandline.OscCommand):
    """
    Make a package on OBS side.
    The primary goal is to provide a convenient way for creating new package with scmsync enabled
    """

    name = "rmkpac"

    def init_arguments(self):

        self.add_argument(
            "project",
            help="Name of the project or . for current directory",
        )

        self.add_argument(
            "package",
            help="Name of the new package",
        )

        self.add_argument(
            "--scmsync",
            help="URL to put to the scmsync tag in _meta file",
        )

        self.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Overwrite existing package, if any",
        )

    def run(self, args):
        from osc import obs_api
        from osc.output import tty
        from osc.store import get_store

        package = args.package

        if not package:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Package is empty")
            sys.exit(1)

        if args.project == ".":
            store = get_store(".")
            store.assert_is_project()
            project = store.project
        else:
            project = args.project

        if not project:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Project is empty")
            sys.exit(1)

        # reject if the project meta has scmsync configured
        prj = obs_api.Project.from_api(args.apiurl, project)

        if prj.scmsync:
            raise RuntimeError(
                "rmkpac cannot create package for projects managed in Git (the <scmsync> element is set in the project meta)"
            )

        # reject if the package exists unless --force is set
        if not args.force:
            pkg = None
            try:
                pkg = obs_api.Package.from_api(args.apiurl, project, package)
            except HTTPError as e:
                if e.code != 404:
                    raise

            if pkg:
                print(f"{tty.colorize('ERROR', 'red,bold')}: Package already exists")
                sys.exit(1)

        pkg = obs_api.Package(name=package, project=project)
        pkg.scmsync = args.scmsync
        pkg.to_api(args.apiurl)
