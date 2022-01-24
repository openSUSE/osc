import os

from steps import osc


# doesn't do anything, just points osc to localhost
class FakeKanku:
    ip = "localhost"


def before_all(context):
    context.fixtures = os.path.join(os.path.dirname(__file__), "..", "fixtures")
    context.kanku = FakeKanku()
    context.osc = osc.Osc(context)


def after_all(context):
    del context.osc
    del context.kanku
    del context.fixtures
