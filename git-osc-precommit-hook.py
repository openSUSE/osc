#!/usr/bin/env python3

"""
This wrapper allows git-osc-precommit-hook to be called from the source directory during development.
"""

import osc.babysitter

osc.babysitter.gitOscPrecommitHook()
