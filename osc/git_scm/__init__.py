import sys

from .store import GitStore


def warn_experimental():
    print("WARNING: Using EXPERIMENTAL support for git scm. The functionality may change or disappear without a prior notice!", file=sys.stderr)
