import sys

from .store import GitStore
from .store import LocalGitStore


def warn_experimental():
    print("WARNING: Using EXPERIMENTAL support for git scm. The functionality may change or disappear without a prior notice!", file=sys.stderr)
