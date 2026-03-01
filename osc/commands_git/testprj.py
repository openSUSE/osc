import sys
import osc.commandline_git


class TestPrjCommand(osc.commandline_git.GitObsCommand):
    """
    Create test project in OBS linking git packages
    """

    name = "testprj"

    def init_arguments(self):
        self.add_argument(
            "-a",
            "--api-url",
            help="OBS api url, defaults to api.opensuse.org",
            default="api.opensuse.org",
        )
        self.add_argument(
            "-p",
            "--prj",
            help="OBS base project to copy config from, defaults to openSUSE:Factory",
        )
        self.add_argument(
            "-b",
            "--branch",
            help="Git branch to use",
        )
        self.add_argument(
            "-f",
            "--fork",
            action="store_true",
            help="Fork gitea pkg repos in your user home, defaults to False",
            default=False,
        )
        self.add_argument(
            "prj_name",
            help="test project name to create in home:USER:$prj_name",
        )
        self.add_argument(
            "pkg_repo",
            nargs="*",
            help="pkg gitea ref, it should be [org/]repo[#branch]",
        )

    def run(self, args):
        from osc import conf

        self.output = []
        self.apiurl = conf.sanitize_apiurl(args.api_url)
        self.args = args
        self.weburl = self.apiurl.replace("api", "build", count=1)

        conf.get_config()
        self.user = conf.get_apiurl_usr(self.apiurl)

        project = f"home:{self.user}:{self.args.prj_name}"
        self.create_project(project)
        self.output.append(f"OBS test project created: {project}")
        self.output.append(f"{self.weburl}/project/show/{project}")
        self.output.append("")

        self.num_entries = 0
        self.failed_entries = []
        for repo in args.pkg_repo:
            repo, branch = self.parse_repo(repo)
            package, scm = self.create_package(project, repo, branch)
            self.output.append(f" * Linked pkg: {package} <- {scm}")

        print()
        for line in self.output:
            print(line, file=sys.stderr)

    def create_project(self, project):
        from osc.util.xml import ET
        from osc.core import edit_meta, xml_fromstring, show_project_meta

        # Get base project meta
        if self.args.prj:
            meta_data = b"".join(show_project_meta(self.apiurl, self.args.prj))
            root = xml_fromstring(meta_data)
            repos = "\n".join(ET.tostring(i).decode() for i in root.findall("repository"))
        else:
            repos = """
            <repository name="openSUSE_Tumbleweed">
              <path project="openSUSE:Tumbleweed" repository="standard"/>
              <arch>x86_64</arch>
            </repository>
            """

        data = f"""
<project name="{project}">
  <title>Test project gitea</title>
  <description/>
  <person userid="{self.user}" role="maintainer"/>
  {repos}
</project>
"""

        # Create the project in OBS
        edit_meta(metatype="prj", data=data, apiurl=self.apiurl, path_args=(project,))

    def create_package(self, project, repo, branch):
        from osc.core import edit_meta

        package = repo.repo
        if self.args.fork:
            scm = self.fork(repo, branch, self.args.branch)
        else:
            scm = f"{repo.clone_url}#{branch}"

        # Create the package in OBS
        data = f"""
<package name="{package}" project="{project}">
  <title/>
  <description/>
  <person userid="{self.user}" role="maintainer"/>
  <scmsync>{scm}</scmsync>
</package>
            """

        edit_meta(metatype="pkg", data=data, apiurl=self.apiurl, path_args=(project, package))

        return package, scm

    def fork(self, repo, base_branch, new_branch=None):
        from osc import gitea_api

        owner, repo = repo.owner, repo.repo
        print(f"Forking git repo {owner}/{repo} ...", file=sys.stderr)
        try:
            repo_obj = gitea_api.Fork.create(self.gitea_conn, owner, repo)
            fork_owner = repo_obj.owner
            fork_repo = repo_obj.repo
            print(f" * Fork created: {fork_owner}/{fork_repo}", file=sys.stderr)
            self.num_entries += 1
        except gitea_api.ForkExists as e:
            fork_owner = e.fork_owner
            fork_repo = e.fork_repo
            print(f" * Fork already exists: {fork_owner}/{fork_repo}", file=sys.stderr)
            self.num_entries += 1
        except gitea_api.GiteaException as e:
            if e.status == 404:
                print(f" * ERROR: Repo doesn't exist: {owner}/{repo}", file=sys.stderr)
                self.failed_entries.append(f"{owner}/{repo}")
                return None
            raise

        r = gitea_api.Repo.get(self.gitea_conn, fork_owner, fork_repo)
        if new_branch:
            try:
                gitea_api.Branch.create(
                    self.gitea_conn, fork_owner, fork_repo, new_branch_name=new_branch, old_ref_name=base_branch
                )
            except gitea_api.BranchExists:
                print(
                    f" * Warning: Branch already exists, not creating it: {fork_owner}/{fork_repo}#{new_branch}",
                    file=sys.stderr,
                )

        branch = new_branch or base_branch
        return f"{r.clone_url}#{branch}"

    def parse_repo(self, repo):
        """
        Convert org/repo#branch into gitea repo
        org and branch are optional, default org is "pool" and default
        branch is the default branch configured in gitea.

        returns [Repo, branch]
        """
        from osc import gitea_api

        org = "pool"
        if "/" in repo:
            org, repo = repo.split("/", maxsplit=1)
        if "#" in repo:
            repo, branch = repo.split("#", maxsplit=1)
        else:
            branch = None

        r = gitea_api.Repo.get(self.gitea_conn, org, repo)
        return r, branch or r.default_branch
