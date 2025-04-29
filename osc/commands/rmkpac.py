import sys
import osc.commandline
from urllib.error import HTTPError


class Rmkpaccommand(osc.commandline.OscCommand):
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
            help="Url to put to the scmsync tag in _meta file",
        )

        self.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Overwrite existing package, if any",
        )

    def run(self, args):
        from pathlib import Path
        from pathlib import PurePath
        from osc import conf as osc_conf
        from osc import obs_api
        from osc import oscerr
        from osc.output import tty
        from osc.core import is_project_dir

        project_dir = ""
        package = args.package

        if not package:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Package is empty")
            sys.exit(1)

        if args.project != ".":
            project_dir = args.project
        else:
            project_dir = str(Path.cwd())
            if not is_project_dir(project_dir):
                raise oscerr.WrongArgs(f"'{project_dir}' is no project working copy")
            project_dir = PurePath(project_dir).name

        if not project_dir:
            print(f"{tty.colorize('ERROR', 'red,bold')}: Project is empty")
            sys.exit(1)

        # reject if the project meta has scmsync configured
        prj = obs_api.Project.from_api(args.apiurl, project_dir)

        if prj.scmsync:
            raise RuntimeError(
                "rmkpac cannot create package for projects managed in Git (the <scmsync> element is set in the project meta)"
            )

        # reject if the package exists unless --force is set
        if not args.force:
            pkg = None
            try:
                pkg = obs_api.Package.from_api(args.apiurl, project_dir, package)
            except HTTPError as e:
                if e.code != 404:
                    raise
                pkg = None

            if pkg:
                print(f"{tty.colorize('ERROR', 'red,bold')}: Package already exists")
                sys.exit(1)

        if args.scmsync:
            p = obs_api.Package(name=package, project=project_dir, scmsync=args.scmsync)
        else:
            p = obs_api.Package(name=package, project=project_dir)
        p.to_api(args.apiurl)
