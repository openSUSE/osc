import json
import sys

import osc.commandline_git


class ApiCommand(osc.commandline_git.GitObsCommand):
    """
    Make an arbitrary request to API
    """

    name = "api"

    def init_arguments(self):
        self.add_argument(
            "-X",
            "--method",
            choices=["GET", "HEAD", "POST", "PATCH", "PUT"],
            default="GET",
        )
        self.add_argument(
            "url",
        )
        self.add_argument("--data")

    def run(self, args):
        from osc import gitea_api
        from osc.output import tty

        self.print_gitea_settings()

        url = self.gitea_conn.makeurl(args.url)

        json_data = None
        if args.data:
            json_data = json.loads(args.data)

        response = self.gitea_conn.request(
            method=args.method, url=url, json_data=json_data
        )
        print(tty.colorize("Response:", "white,bold"), file=sys.stderr)
        if response.headers.get("Content-Type", "").startswith("application/json;"):
            print(
                json.dumps(
                    json.loads(response.data),
                    indent=4,
                    sort_keys=True,
                )
            )
        else:
            print(response.data.decode("utf-8"))
