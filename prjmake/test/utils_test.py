# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest

from oscpluginprjmake import utils
import os

def suite():
    return unittest.makeSuite(TestUtils)

class TestUtils(unittest.TestCase):

    def test_buildroot_unique(self):
        self.assertFalse(utils.is_buildroot_unique())
        os.environ['OSC_BUILD_ROOT'] = '/var/tmp/%(package)s'
        self.assertTrue(utils.is_buildroot_unique())

if __name__ == '__main__':
    unittest.main()

# vim: et ts=4 sw=4
