import os
import re
import shutil
import tempfile
import time

import behave
import ruamel.yaml

from steps.common import debug
from steps.common import run_in_context


class CommandBase:
    CONFIG_NAME: str

    def __init__(self, context):
        if not hasattr(context, "podman"):
            raise RuntimeError("context doesn't have 'podman' object set")

        self.context = context
        debug(self.context, f"{self.__class__.__name__}.__init__()")
        self.temp = None
        self.clear()

    def __del__(self):
        try:
            shutil.rmtree(self.temp)
        except Exception:
            pass

    def clear(self):
        debug(self.context, f"{self.__class__.__name__}.clear()")
        if self.temp:
            shutil.rmtree(self.temp)
        self.temp = tempfile.mkdtemp(prefix="osc_behave_")
        self.config = os.path.join(self.temp, self.CONFIG_NAME)
        self.write_config()

    def write_config(self, **kwargs):
        raise NotImplementedError()


class Osc(CommandBase):
    CONFIG_NAME = "oscrc"

    def write_config(self, username=None, password=None):
        with open(self.config, "w") as f:
            f.write("[general]\n")
            f.write("\n")
            f.write(f"[https://localhost:{self.context.podman.container.ports['obs_https']}]\n")
            f.write(f"user={username or 'Admin'}\n")
            f.write(f"pass={password or 'opensuse'}\n")
            f.write("credentials_mgr_class=osc.credentials.PlaintextConfigFileCredentialsManager\n")
            f.write("sslcertck=0\n")
            if not any((username, password)):
                f.write("http_headers =\n")
                # avoid the initial 401 response by using proxy auth
                f.write("    X-Username: Admin\n")

    def get_cmd(self):
        osc_cmd = self.context.config.userdata.get("osc", "osc")
        cmd = [osc_cmd]
        cmd += ["--config", self.config]
        cmd += ["-A", f"https://localhost:{self.context.podman.container.ports['obs_https']}"]
        return cmd


class GitOscPrecommitHook(CommandBase):
    CONFIG_NAME = "oscrc"

    def write_config(self, username=None, password=None):
        with open(self.config, "w") as f:
            f.write("[general]\n")
            f.write("\n")
            f.write(f"[https://localhost:{self.context.podman.container.ports['obs_https']}]\n")
            f.write(f"user={username or 'Admin'}\n")
            f.write(f"pass={password or 'opensuse'}\n")
            f.write("credentials_mgr_class=osc.credentials.PlaintextConfigFileCredentialsManager\n")
            f.write("sslcertck=0\n")
            if not any((username, password)):
                f.write("http_headers =\n")
                # avoid the initial 401 response by using proxy auth
                f.write("    X-Username: Admin\n")

    def get_cmd(self):
        git_osc_precommit_hook_cmd = self.context.config.userdata.get(
            "git-osc-precommit-hook", "git-osc-precommit-hook"
        )
        cmd = [git_osc_precommit_hook_cmd]
        cmd += ["--config", self.config]
        cmd += ["-A", f"https://localhost:{self.context.podman.container.ports['obs_https']}"]
        return cmd


class GitObs(CommandBase):
    CONFIG_NAME = "config.yml"

    def write_config(self):
        data = {
            "logins": [
                {
                    "name": "admin",
                    "url": f"http://localhost:{self.context.podman.container.ports['gitea_http']}",
                    "user": "Admin",
                    "token": 40 * "1",
                    "ssh_key": f"{self.context.fixtures}/ssh-keys/admin",
                    "default": True,
                },
                {
                    "name": "alice",
                    "url": f"http://localhost:{self.context.podman.container.ports['gitea_http']}",
                    "user": "Alice",
                    "token": 40 * "a",
                    "ssh_key": f"{self.context.fixtures}/ssh-keys/alice",
                    "default": False,
                },
                {
                    "name": "bob",
                    "url": f"http://localhost:{self.context.podman.container.ports['gitea_http']}",
                    "user": "Bob",
                    "token": 40 * "b",
                    "ssh_key": f"{self.context.fixtures}/ssh-keys/bob",
                    "default": False,
                },
            ],
        }
        with open(self.config, "w") as f:
            yaml = ruamel.yaml.YAML()
            yaml.default_flow_style = False
            yaml.dump(data, f)

    def get_cmd(self):
        git_obs_cmd = self.context.config.userdata.get("git-obs", "git-obs")
        cmd = [git_obs_cmd]
        cmd += ["--gitea-config", self.config]
        cmd += ["-G", f"admin"]
        return cmd


@behave.step("I execute osc with args \"{args}\"")
def step_impl(context, args):
    args = args.format(context=context)
    cmd = context.osc.get_cmd() + [args]
    cmd = " ".join(cmd)
    run_in_context(context, cmd, can_fail=True)
    # remove InsecureRequestWarning that is irrelevant to the tests
    context.cmd_stderr = re.sub(r"^.*InsecureRequestWarning.*\n  warnings.warn\(\n", "", context.cmd_stderr)


@behave.step("I execute git-obs with args \"{args}\"")
def step_impl(context, args):
    args = args.format(context=context)
    cmd = context.git_obs.get_cmd() + [args]
    cmd = " ".join(cmd)
    run_in_context(context, cmd, can_fail=True)
    # remove InsecureRequestWarning that is irrelevant to the tests
    context.cmd_stderr = re.sub(r"^.*InsecureRequestWarning.*\n  warnings.warn\(\n", "", context.cmd_stderr)


@behave.step('I execute git-osc-precommit-hook with args "{args}"')
def step_impl(context, args):
    args = args.format(context=context)
    cmd = context.git_osc_precommit_hook.get_cmd() + [args]
    cmd = " ".join(cmd)
    run_in_context(context, cmd, can_fail=True)
    # remove InsecureRequestWarning that is irrelevant to the tests
    context.cmd_stderr = re.sub(r"[^\n]*InsecureRequestWarning.*\n  warnings.warn\(\n", "", context.cmd_stderr)
    context.cmd_stderr = re.sub(
        r"WARNING: Using EXPERIMENTAL support for git scm. The functionality may change or disappear without a prior notice!\n",
        "",
        context.cmd_stderr,
    )


@behave.step("I configure osc user \"{username}\" with password \"{password}\"")
def step_impl(context, username, password):
    context.osc.write_config(username=username, password=password)


@behave.step('I wait for osc results for "{project}" "{package}"')
def step_impl(context, project, package):
    args = f"results {project} {package} --csv --format='%(code)s,%(dirty)s'"
    cmd = context.osc.get_cmd() + [args]
    cmd = " ".join(cmd)

    while True:
        # wait for a moment before checking the status even for the first time
        # for some reason, packages appear to be "broken" for a while after they get commited
        time.sleep(5)

        run_in_context(context, cmd, can_fail=True)
        results = []
        for line in context.cmd_stdout.splitlines():
            code, dirty = line.split(",")
            dirty = dirty.lower() == "true"
            results.append((code, dirty))

        if all((code == "succeeded" and not dirty for code, dirty in results)):
            # all builds have succeeded and all dirty flags are false
            break

        if any((code in ("unresolvable", "failed", "broken", "blocked", "locked", "excluded") and not dirty for code, dirty in results)):
            # failed build with dirty flag false
            raise AssertionError("Package build failed:\n" + context.cmd_stdout)
