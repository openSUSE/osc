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
    proc = context.podman.container.exec(["bash", "-c", "find /srv/www/obs/api/log/ /srv/obs/log/ -name '*.log' -exec truncate --size=0 {} \\;"])


def after_scenario(context, scenario):
    if scenario.status == Status.failed:
        # the scenario has failed, dump server logs
        print("===== BEGIN: server logs ======")
        proc = context.podman.container.exec(["bash", "-c", "tail -n +1 /srv/www/obs/api/log/*.log /srv/obs/log/*.log"])
        print(proc.stdout)
        print("===== END: server logs ======")

    if "destructive" in scenario.tags:
        # start a new container after a destructive test
        # we must use an existing podman instance defined in `before_all` due to context attribute life-cycle:
        # https://behave.readthedocs.io/en/stable/context_attributes.html
        context.podman.new_container()
    context.osc.clear()
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

    # absolute path to .../behave/fixtures
    context.fixtures = os.path.join(os.path.dirname(__file__), "..", "fixtures")

    podman_max_containers = context.config.userdata.get("podman_max_containers", None)
    if podman_max_containers:
        podman_max_containers = int(podman_max_containers)
        context.podman = podman.ThreadedPodman(context, container_name_prefix="osc-behave-", max_containers=podman_max_containers)
    else:
        context.podman = podman.Podman(context, container_name="osc-behave")
    context.osc = osc.Osc(context)


def after_all(context):
    del context.osc
    context.podman.kill()
    del context.podman
    del context.fixtures
