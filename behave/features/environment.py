import os

from steps import kanku
from steps import osc
from steps import common


def before_step(context, step):
    pass


def after_step(context, step):
    pass


def before_scenario(context, scenario):
    context.osc = osc.Osc(context)


def after_scenario(context, scenario):
    common.check_exit_code(context)
    del context.osc


def before_feature(context, feature):
    # decorate Feature with @no-snapshot to avoid doing a snapshot rollback
    if "no-snapshot" not in feature.tags:
        context.kanku.revert_to_snapshot()


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

    kankufile = os.path.join(os.path.dirname(__file__), "..", "KankuFile")
    context.kanku = kanku.Kanku(context, kankufile)

    # This fails if the snapshot exists already.
    # It's ok in most cases, because it's the same snapshot we'd normally create.
    context.kanku.create_snapshot()


def after_all(context):
    del context.kanku
    del context.fixtures
