import os

from steps import common
from steps import osc
from steps import podman


def before_step(context, step):
    pass


def after_step(context, step):
    pass


def before_scenario(context, scenario):
    pass


def after_scenario(context, scenario):
    if "destructive" in scenario.tags:
        # start a new container after a destructive test
        # we must use an existing podman instance defined in `before_all` due to context attribute life-cycle:
        # https://behave.readthedocs.io/en/stable/context_attributes.html
        context.podman.restart()
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

    context.podman = podman.Podman(context)
    context.osc = osc.Osc(context)


def after_all(context):
    del context.osc
    context.podman.kill()
    del context.podman
    del context.fixtures
