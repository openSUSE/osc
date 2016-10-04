# Copyright (c) 2016 Ericsson AB
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or version 3 (at your option).
#

import unittest

from oscpluginprjmake import buildinfothread

def suite():
    return unittest.makeSuite(TestJobSplit)

class TestJobSplit(unittest.TestCase):

    def test_zero(self):
        job_indexes = buildinfothread.split_jobs(0, 0)
        self.assertEqual(job_indexes, [])
        job_indexes = buildinfothread.split_jobs(0, 3)
        self.assertEqual(job_indexes, [(0, 0), (0, 0), (0, 0)])
        job_indexes = buildinfothread.split_jobs(3, 0)
        self.assertEqual(job_indexes, [])

    def test_one(self):
        job_indexes = buildinfothread.split_jobs(1, 4)
        self.assertEqual(job_indexes, [(0, 1), (1, 1), (1, 1), (1, 1)])

    def test_even(self):
        job_indexes = buildinfothread.split_jobs(6, 3)
        self.assertEqual(job_indexes, [(0, 2), (2, 4), (4, 6)])
        job_indexes = buildinfothread.split_jobs(2, 2)
        self.assertEqual(job_indexes, [(0, 1), (1, 2)])

    def test_odd(self):
        job_indexes = buildinfothread.split_jobs(5, 3)
        self.assertEqual(job_indexes, [(0, 2), (2, 4), (4, 5)])
        job_indexes = buildinfothread.split_jobs(1, 2)
        self.assertEqual(job_indexes, [(0, 1), (1, 1)])

if __name__ == '__main__':
    unittest.main()

# vim: et ts=4 sw=4
