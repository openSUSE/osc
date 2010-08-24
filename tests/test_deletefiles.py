import osc.core
import osc.oscerr
import os
import sys
from common import GET, OscTestCase

FIXTURES_DIR = os.path.join(os.getcwd(), 'deletefile_fixtures')

def suite():
    import unittest
    return unittest.makeSuite(TestDeleteFiles)

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
        self.__check_deletelist('foo\n')
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
        self._check_list('_to_be_added', 'toadd1\nmerge\n')
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
        self.assertTrue(os.path.exists(os.path.join('.osc', '_in_conflict')))
        self._check_status(p, 'foo', 'C')

    def testDeleteModifiedForce(self):
        """force deletion modified file ('nochange') from wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('nochange', force=True)
        self.__check_ret(ret, True, 'M')
        self.assertFalse(os.path.exists('nochange'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'nochange')))
        self.__check_deletelist('nochange\n')
        self._check_status(p, 'nochange', 'D')

    def testDeleteUnversionedForce(self):
        """delete an unversioned file ('toadd2') from the wc (with force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd2', force=True)
        self.__check_ret(ret, True, '?')
        self.assertFalse(os.path.exists('toadd2'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self.assertRaises(IOError, p.status, 'toadd2')

    def testDeleteAddedForce(self):
        """delete an added file ('toadd1') from the wc (with force)"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        ret = p.delete_file('toadd1', force=True)
        self.__check_ret(ret, True, 'A')
        self.assertFalse(os.path.exists('toadd1'))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))
        self.assertRaises(IOError, p.status, 'toadd1')

    def testDeleteReplacedForce(self):
        """delete an added file ('merge') from the wc (with force)"""
        self._change_to_pkg('replace')
        p = osc.core.Package('.')
        ret = p.delete_file('merge', force=True)
        self.__check_ret(ret, True, 'R')
        self.assertFalse(os.path.exists('merge'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'merge')))
        self.__check_deletelist('merge\n')
        self._check_list('_to_be_added', 'toadd1\n')
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
        self.__check_deletelist('foo\n')
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
        self.__check_deletelist('foo\nmerge\n')

    def testDeleteAlreadyDeleted(self):
        """delete already deleted file from the wc"""
        self._change_to_pkg('already_deleted')
        p = osc.core.Package('.')
        ret = p.delete_file('foo')
        self.__check_ret(ret, True, 'D')
        self.assertFalse(os.path.exists('foo'))
        self.assertTrue(os.path.exists(os.path.join('.osc', 'foo')))
        self.__check_deletelist('foo\n')
        self._check_status(p, 'foo', 'D')

    def __check_ret(self, ret, exp1, exp2):
        self.assertTrue(len(ret) == 2)
        self.assertTrue(ret[0] == exp1)
        self.assertTrue(ret[1] == exp2)

    def __check_deletelist(self, exp):
        self._check_list('_to_be_deleted', exp)

if __name__ == '__main__':
    import unittest
    unittest.main()
