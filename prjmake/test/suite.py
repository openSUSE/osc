#!/usr/bin/env python
#
# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest
import sys

import buildinfothread_test
import buildorder_test
import buildstate_test
import datatypes_test
import settings_test
import utils_test

suite = unittest.TestSuite()
suite.addTests(buildinfothread_test.suite())
suite.addTests(buildorder_test.suite())
suite.addTests(buildstate_test.suite())
suite.addTests(datatypes_test.suite())
suite.addTests(settings_test.suite())
suite.addTests(utils_test.suite())

sys.exit(not unittest.TextTestRunner(verbosity = 1).run(suite).wasSuccessful())
