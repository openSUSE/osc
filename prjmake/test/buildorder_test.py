# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest

from oscpluginprjmake import buildorder

def suite():
    return unittest.makeSuite(TestBuildOrder)

class TestBuildOrder(unittest.TestCase):

    def test_circular_dep_check(self):
        deps = {
            'a': ['b', 'c', 'd'],
            'b': ['d'],
            'c': [],
            'd': ['c', 'a']
        }
        rdeps = {
            'a': ['d'],
            'b': ['a'],
            'c': ['a', 'd'],
            'd': ['a']
        }
        self.assertTrue(buildorder.detect_circular_dep('a', 'd', deps, rdeps))
        self.assertFalse(buildorder.detect_circular_dep('a', 'b', deps, rdeps))

if __name__ == '__main__':
    unittest.main()


# vim: et ts=4 sw=4
