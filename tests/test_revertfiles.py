import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'revertfile_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestRevertFiles)


class TestRevertFiles(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def testRevertUnchanged(self):
        """revert an unchanged file (state == ' ')"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        self.assertRaises(osc.oscerr.OscIOError, p.revert, 'toadd2')
        self._check_status(p, 'toadd2', '?')

    def testRevertModified(self):
        """revert a modified file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('nochange')
        self.__check_file('nochange')
        self._check_status(p, 'nochange', ' ')

    def testRevertAdded(self):
        """revert an added file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('toadd1')
        self.assertTrue(os.path.exists('toadd1'))
        self._check_addlist('replaced\naddedmissing\n')
        self._check_status(p, 'toadd1', '?')

    def testRevertDeleted(self):
        """revert a deleted file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('somefile')
        self.__check_file('somefile')
        self._check_deletelist('deleted\n')
        self._check_status(p, 'somefile', ' ')

    def testRevertMissing(self):
        """revert a missing (state == '!') file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('missing')
        self.__check_file('missing')
        self._check_status(p, 'missing', ' ')

    def testRevertMissingAdded(self):
        """revert a missing file which was added to the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('addedmissing')
        self._check_addlist('toadd1\nreplaced\n')
        self.assertRaises(osc.oscerr.OscIOError, p.status, 'addedmissing')

    def testRevertReplaced(self):
        """revert a replaced (state == 'R') file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('replaced')
        self.__check_file('replaced')
        self._check_addlist('toadd1\naddedmissing\n')
        self._check_status(p, 'replaced', ' ')

    def testRevertConflict(self):
        """revert a file which is in the conflict state"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.revert('foo')
        self.__check_file('foo')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_in_conflict')))
        self._check_status(p, 'foo', ' ')

    def testRevertSkipped(self):
        """revert a skipped file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        self.assertRaises(osc.oscerr.OscIOError, p.revert, 'skipped')

    def __check_file(self, fname):
        storefile = os.path.join('.osc', fname)
        self.assertTrue(os.path.exists(fname))
        self.assertTrue(os.path.exists(storefile))
        self.assertFilesEqual(fname, storefile)


if __name__ == '__main__':
    unittest.main()
