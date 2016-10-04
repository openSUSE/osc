# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest

from oscpluginprjmake import buildstate

def suite():
    return unittest.makeSuite(TestBuildState)

class TestBuildState(unittest.TestCase):

    def test_placeholder(self):
        self.assertTrue(True)

# vim: et ts=4 sw=4
