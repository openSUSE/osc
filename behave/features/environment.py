import os

from behave.model_core import Status

from steps import common
from steps import osc
from steps import podman


def before_step(context, step):
    pass


def after_step(context, step):
    pass


def before_scenario(context, scenario):
    # truncate the logs before running any commands
    proc = context.podman.container.exec(["bash", "-c", "find /srv/www/obs/api/log/ /srv/obs/log/ /var/log/gitea/ -name '*.log' -exec truncate --size=0 {} \\;"])


def after_scenario(context, scenario):
    if scenario.status == Status.failed:
        # the scenario has failed, dump server logs
        print("===== BEGIN: server logs ======")
        proc = context.podman.container.exec(["bash", "-c", "tail -n +1 /srv/www/obs/api/log/*.log /srv/obs/log/*.log /var/log/gitea/*.log"])
        print(proc.stdout)
        print("===== END: server logs ======")

    if "destructive" in scenario.tags:
        # start a new container after a destructive test
        # we must use an existing podman instance defined in `before_all` due to context attribute life-cycle:
        # https://behave.readthedocs.io/en/stable/context_attributes.html
        context.podman.new_container()

    context.osc.clear()
    context.git_obs.clear()
    context.git_osc_precommit_hook.clear()

    common.check_exit_code(context)


def before_feature(context, feature):
    pass


def after_feature(context, feature):
    pass


def after_tag(context, tag):
    pass


def before_all(context):
    # convert path to osc executable to an absolute path to avoid relative path issues
    if "osc" in context.config.userdata:
        context.config.userdata["osc"] = os.path.abspath(os.path.expanduser(context.config.userdata["osc"]))

    if "git-obs" in context.config.userdata:
        context.config.userdata["git-obs"] = os.path.abspath(os.path.expanduser(context.config.userdata["git-obs"]))

    if "git-osc-precommit-hook" in context.config.userdata:
        context.config.userdata["git-osc-precommit-hook"] = os.path.abspath(
            os.path.expanduser(context.config.userdata["git-osc-precommit-hook"])
        )

    # absolute path to .../behave/fixtures
    context.fixtures = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "fixtures"))

    # fix ssh-key perms
    ssh_dir = os.path.join(context.fixtures, "ssh-keys")
    for fn in os.listdir(ssh_dir):
        ssh_key = os.path.join(ssh_dir, fn)
        os.chmod(ssh_key, 0o600)

    podman_max_containers = context.config.userdata.get("podman_max_containers", None)
    if podman_max_containers:
        podman_max_containers = int(podman_max_containers)
        context.podman = podman.ThreadedPodman(context, container_name_prefix="osc-behave-", max_containers=podman_max_containers)
    else:
        context.podman = podman.Podman(context, container_name="osc-behave")
    context.osc = osc.Osc(context)
    context.git_obs = osc.GitObs(context)
    context.git_osc_precommit_hook = osc.GitOscPrecommitHook(context)


def after_all(context):
    del context.git_osc_precommit_hook
    del context.git_obs
    del context.osc
    context.podman.kill()
    del context.podman
    del context.fixtures
