import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'project_package_status_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestPackageStatus)


class TestPackageStatus(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def test_allfiles(self):
        """get the status of all files in the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        exp_st = [('A', 'add'), ('?', 'exists'), ('D', 'foo'), ('!', 'merge'), ('R', 'missing'),
                  ('!', 'missing_added'), ('M', 'nochange'), ('S', 'skipped'), (' ', 'test')]
        st = p.get_status()
        self.assertEqual(exp_st, st)

    def test_todo(self):
        """
        get the status of some files in the wc.
        """
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['test', 'missing_added', 'foo']
        exp_st = [('D', 'foo'), ('!', 'missing_added')]
        st = p.get_status(False, ' ')
        self.assertEqual(exp_st, st)

    def test_todo_noexcl(self):
        """ get the status of some files in the wc. """
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['test', 'missing_added', 'foo']
        exp_st = [('D', 'foo'), ('!', 'missing_added'), (' ', 'test')]
        st = p.get_status()
        self.assertEqual(exp_st, st)

    def test_exclude_state(self):
        """get the status of all files in the wc but exclude some states"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        exp_st = [('A', 'add'), ('?', 'exists'), ('D', 'foo')]
        st = p.get_status(False, '!', 'S', ' ', 'M', 'R')
        self.assertEqual(exp_st, st)

    def test_nonexistent(self):
        """get the status of a non existent file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.todo = ['doesnotexist']
        self.assertRaises(osc.oscerr.OscIOError, p.get_status)

    def test_conflict(self):
        """get status of the wc (one file in conflict state)"""
        self._change_to_pkg('conflict')
        p = osc.core.Package('.')
        exp_st = [('C', 'conflict'), ('?', 'exists'), (' ', 'test')]
        st = p.get_status()
        self.assertEqual(exp_st, st)

    def test_excluded(self):
        """get status of the wc (ignore excluded files); package has state ' '"""
        self._change_to_pkg('excluded')
        p = osc.core.Package('.')
        exp_st = [('?', 'exists'), ('M', 'modified')]
        st = p.get_status(False, ' ')
        self.assertEqual(exp_st, st)

    def test_noexcluded(self):
        """get status of the wc (include excluded files)"""
        self._change_to_pkg('excluded')
        p = osc.core.Package('.')
        exp_st = [('?', '_linkerror'), ('?', 'exists'), ('?', 'foo.orig'), ('M', 'modified'), (' ', 'test')]
        st = p.get_status(True)
        self.assertEqual(exp_st, st)


if __name__ == '__main__':
    unittest.main()
