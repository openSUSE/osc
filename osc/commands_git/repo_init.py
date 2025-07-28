import sys

import osc.commandline_git


class RepoInitCommand(osc.commandline_git.GitObsCommand):
    """
    Init a git repo

    Initialize or update a package git repo, setting .gitignore, .gitattributes and other files from a template.

    """

    name = "init"
    parent = "RepoCommand"

    def init_arguments(self):
        self.add_argument(
            "-a",
            "--anonymous",
            action="store_true",
            default=None,
            help="Clone anonymously via the http protocol",
        )

        self.add_argument(
            "path",
            default=".",
            help="Destination path to a directory which needs to be initialized. Default is current working directory",
        )

        self.add_argument(
            "-t",
            "--template",
            default=None,
            help="Path to a template directory url to git repository",
        )

        self.add_argument(
            "-i",
            "--ssh-key",
            help="Path to a private SSH key (identity file)",
        )

        self.add_argument(
            "--no-ssh-strict-host-key-checking",
            action="store_true",
            help="Set 'StrictHostKeyChecking no' ssh option",
        )

    def run(self, args):
        import os
        import subprocess
        from pathlib import Path
        from osc.output import tty
        from osc import gitea_api
        from osc import git_scm

        template = args.template
        if not template:
            template = self.gitea_conf.git_obs_repo_init_template()

        if not template:
            print("Template must be a valid path or url", file=sys.stderr)
            exit(1)

        dest = args.path
        if not dest:
            dest = "."

        if not dest:
            print(f"Destination folder ({dest}) must be a valid path", file=sys.stderr)
            exit(1)

        if not os.path.isdir(dest):
            os.mkdir(dest)

        if not os.path.isdir(dest):
            print(f"Destination folder ({dest}) must be a valid path", file=sys.stderr)
            exit(1)

        gitea_owner, gitea_repo = (None, None)
        if "://" in template or (not Path(template).is_dir()):
            gitea_owner, gitea_repo = gitea_api.Git.split_owner_repo(template)

        tmp_dir = None

        if gitea_repo:  # i.e. remote template - need to clone it to a temp folder
            import tempfile

            tmp_dir = tempfile.TemporaryDirectory(prefix="osc_git_init_template")
            try:
                gitea_api.Repo.clone(
                    self.gitea_conn,
                    gitea_owner,
                    gitea_repo,
                    directory=tmp_dir.name,
                    quiet=True,
                    use_http=(args.anonymous or self.gitea_login.git_uses_http),
                    add_remotes=True,
                    ssh_private_key_path=args.ssh_key or self.gitea_login.ssh_key,
                    ssh_strict_host_key_checking=(not args.no_ssh_strict_host_key_checking),
                    sparse="/.gitattributes /.gitignore /.gitconfig",
                )
            except gitea_api.GiteaException as e:
                if e.status == 404:
                    print(
                        f" * {tty.colorize('ERROR', 'red,bold')}: Repo doesn't exist: {gitea_owner}/{gitea_repo}",
                        file=sys.stderr,
                    )
                    exit(1)
                raise
            except subprocess.CalledProcessError as e:
                print(
                    f" * {tty.colorize('ERROR', 'red,bold')}: git clone of the template {gitea_owner}/{gitea_repo} failed",
                    file=sys.stderr,
                )
                exit(1)

            src = tmp_dir.name
        else:
            src = template

        if not Path(src).is_dir():
            print(f"Template ({src}) must be a valid path or url", file=sys.stderr)
            exit(1)

        if dest == src:
            print(f"Destination folder ({dest}) cannot be the template to iself ({src})", file=sys.stderr)
            exit(1)

        git_scm.GitStore(dest, check=False).obs_git_init(src)

        print("", file=sys.stderr)
