import os
import sys

import osc.commandline
from osc import conf as osc_conf
from osc import conf
from osc.util.helper import raw_input


def _confirm_overwrite(conffile: str) -> bool:
    path = os.path.expanduser(conffile)
    if os.path.exists(path):
        print(f"Config file '{conffile}' already exists.", file=sys.stderr)
        answer = raw_input("Overwrite it? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted: not overwriting existing config.", file=sys.stderr)
            return False
    return True


class InitConfigFullCommand(osc.commandline.OscCommand):
    """
    Generate a new configuration file.
    """

    name = "initconfig"
    aliases = ["ic"]

    def init_arguments(self):
        self.add_argument(
            "--file",
            help="Write the config to this file instead of the default location",
        )
        self.add_argument(
            "--apiurl",
            help="API URL to embed in the config instead of the default one",
        )

    def run(self, args):
        apiurl = args.apiurl or osc_conf.Options().apiurl
        conffile = args.file or osc_conf.identify_conf()

        if not _confirm_overwrite(conffile):
            return  # user chose not to overwrite

        conf.interactive_config_setup(conffile, apiurl, True)
