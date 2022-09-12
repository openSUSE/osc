import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'deletefile_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestDeleteFiles)


class TestDeleteFiles(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def testSimpleRemove(self):
        """delete a file ('foo') from the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('foo')
        self.__check_ret(ret, True, ' ')
        self.assertFalse(os.path.exists('foo'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self._check_deletelist('foo\n')
        self._check_status(p, 'foo', 'D')

    def testDeleteModified(self):
        """delete modified file ('nochange') from the wc (without force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('nochange')
        self.__check_ret(ret, False, 'M')
        self.assertTrue(os.path.exists('nochange'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'nochange')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_status(p, 'nochange', 'M')

    def testDeleteUnversioned(self):
        """delete an unversioned file ('toadd2') from the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd2')
        self.__check_ret(ret, False, '?')
        self.assertTrue(os.path.exists('toadd2'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_status(p, 'toadd2', '?')

    def testDeleteAdded(self):
        """delete an added file ('toadd1') from the wc (without force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd1')
        self.__check_ret(ret, False, 'A')
        self.assertTrue(os.path.exists('toadd1'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_status(p, 'toadd1', 'A')

    def testDeleteReplaced(self):
        """delete an added file ('merge') from the wc (without force)"""
        self._change_to_pkg('replace')
        p = osc.core.Package('.')
        ret = p.delete_file('merge')
        self.__check_ret(ret, False, 'R')
        self.assertTrue(os.path.exists('merge'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_addlist('toadd1\nmerge\n')
        self._check_status(p, 'merge', 'R')

    def testDeleteConflict(self):
        """delete a file ('foo', state='C') from the wc (without force)"""
        self._change_to_pkg('conflict')
        p = osc.core.Package('.')
        ret = p.delete_file('foo')
        self.__check_ret(ret, False, 'C')
        self.assertTrue(os.path.exists('foo'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_conflictlist('foo\n')
        self._check_status(p, 'foo', 'C')

    def testDeleteModifiedForce(self):
        """force deletion modified file ('nochange') from wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('nochange', force=True)
        self.__check_ret(ret, True, 'M')
        self.assertFalse(os.path.exists('nochange'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'nochange')))
        self._check_deletelist('nochange\n')
        self._check_status(p, 'nochange', 'D')

    def testDeleteUnversionedForce(self):
        """delete an unversioned file ('toadd2') from the wc (with force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd2', force=True)
        self.__check_ret(ret, True, '?')
        self.assertFalse(os.path.exists('toadd2'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self.assertRaises(osc.oscerr.OscIOError, p.status, 'toadd2')

    def testDeleteAddedForce(self):
        """delete an added file ('toadd1') from the wc (with force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd1', force=True)
        self.__check_ret(ret, True, 'A')
        self.assertFalse(os.path.exists('toadd1'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))
        self.assertRaises(osc.oscerr.OscIOError, p.status, 'toadd1')

    def testDeleteReplacedForce(self):
        """delete an added file ('merge') from the wc (with force)"""
        self._change_to_pkg('replace')
        p = osc.core.Package('.')
        ret = p.delete_file('merge', force=True)
        self.__check_ret(ret, True, 'R')
        self.assertFalse(os.path.exists('merge'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'merge')))
        self._check_deletelist('merge\n')
        self._check_addlist('toadd1\n')
        self._check_status(p, 'merge', 'D')

    def testDeleteConflictForce(self):
        """delete a file ('foo', state='C') from the wc (with force)"""
        self._change_to_pkg('conflict')
        p = osc.core.Package('.')
        ret = p.delete_file('foo', force=True)
        self.__check_ret(ret, True, 'C')
        self.assertFalse(os.path.exists('foo'))
        self.assertTrue(os.path.exists('foo.r2'))
        self.assertTrue(os.path.exists('foo.mine'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self._check_deletelist('foo\n')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_in_conflict')))
        self._check_status(p, 'foo', 'D')

    def testDeleteMultiple(self):
        """delete mutliple files from the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('foo')
        self.__check_ret(ret, True, ' ')
        ret = p.delete_file('merge')
        self.__check_ret(ret, True, ' ')
        self.assertFalse(os.path.exists('foo'))
        self.assertFalse(os.path.exists('merge'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'merge')))
        self._check_deletelist('foo\nmerge\n')

    def testDeleteAlreadyDeleted(self):
        """delete already deleted file from the wc"""
        self._change_to_pkg('already_deleted')
        p = osc.core.Package('.')
        ret = p.delete_file('foo')
        self.__check_ret(ret, True, 'D')
        self.assertFalse(os.path.exists('foo'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self._check_deletelist('foo\n')
        self._check_status(p, 'foo', 'D')

    def testDeleteAddedMissing(self):
        """
        delete a file which was added to the wc and is removed again
        (via a non osc command). It's current state is '!'
        """
        self._change_to_pkg('delete')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd1')
        self.__check_ret(ret, True, '!')
        self.assertFalse(os.path.exists('toadd1'))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'toadd1')))
        self._check_deletelist('foo\n')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))

    def testDeleteSkippedLocalNotExistent(self):
        """
        delete a skipped file: no local file with that name exists
        """
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('skipped')
        self.__check_ret(ret, False, 'S')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))

    def testDeleteSkippedLocalExistent(self):
        """
        delete a skipped file: a local file with that name exists and will be deleted
        (for instance _service:* files have status 'S' but a local files might exist)
        """
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('skipped_exists')
        self.__check_ret(ret, True, 'S')
        self.assertFalse(os.path.exists('skipped_exists'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))

    def __check_ret(self, ret, exp1, exp2):
        self.assertTrue(len(ret) == 2)
        self.assertTrue(ret[0] == exp1)
        self.assertTrue(ret[1] == exp2)


if __name__ == '__main__':
    unittest.main()
