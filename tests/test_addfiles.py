import os
import sys
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'addfile_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestAddFiles)


class TestAddFiles(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def testSimpleAdd(self):
        """add one file ('toadd1') to the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.addfile('toadd1')
        exp = 'A    toadd1\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', 'toadd1')))
        self._check_status(p, 'toadd1', 'A')
        self._check_addlist('toadd1\n')

    def testSimpleMultipleAdd(self):
        """add multiple files ('toadd1', 'toadd2') to the wc"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.addfile('toadd1')
        p.addfile('toadd2')
        exp = 'A    toadd1\nA    toadd2\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', 'toadd1')))
        self.assertFalse(os.path.exists(os.path.join('.osc', 'toadd2')))
        self._check_status(p, 'toadd1', 'A')
        self._check_status(p, 'toadd2', 'A')
        self._check_addlist('toadd1\ntoadd2\n')

    def testAddVersionedFile(self):
        """add a versioned file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        self.assertRaises(osc.oscerr.PackageFileConflict, p.addfile, 'merge')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))
        self._check_status(p, 'merge', ' ')

    def testAddUnversionedFileTwice(self):
        """add the same file twice"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        p.addfile('toadd1')
        self.assertRaises(osc.oscerr.PackageFileConflict, p.addfile, 'toadd1')
        exp = 'A    toadd1\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFalse(os.path.exists(os.path.join('.osc', 'toadd1')))
        self._check_status(p, 'toadd1', 'A')
        self._check_addlist('toadd1\n')

    def testReplace(self):
        """replace a deleted file ('foo')"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        with open('foo', 'w') as f:
            f.write('replaced file\n')
        p.addfile('foo')
        exp = 'A    foo\n'
        self.assertEqual(sys.stdout.getvalue(), exp)
        self.assertFileContentNotEqual(os.path.join('.osc', 'foo'), 'replaced file\n')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_deleted')))
        self._check_status(p, 'foo', 'R')
        self._check_addlist('foo\n')

    def testAddNonExistentFile(self):
        """add a non existent file"""
        self._change_to_pkg('simple')
        p = osc.core.Package('.')
        self.assertRaises(osc.oscerr.OscIOError, p.addfile, 'doesnotexist')
        self.assertFalse(os.path.exists(os.path.join('.osc', '_to_be_added')))


if __name__ == '__main__':
    unittest.main()
