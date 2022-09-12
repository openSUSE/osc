import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'init_package_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestInitPackage)


class TestInitPackage(OscTestCase):
    def _get_fixtures_dir(self):
        # workaround for git because it doesn't allow empty dirs
        if not os.path.exists(os.path.join(FIXTURES_DIR, 'osctest')):
            os.mkdir(os.path.join(FIXTURES_DIR, 'osctest'))
        return FIXTURES_DIR

    def tearDown(self):
        if os.path.exists(os.path.join(FIXTURES_DIR, 'osctest')):
            os.rmdir(os.path.join(FIXTURES_DIR, 'osctest'))
        super().tearDown()

    def test_simple(self):
        """initialize a package dir"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        osc.core.Package.init_package('http://localhost', 'osctest', 'testpkg', pac_dir)
        storedir = os.path.join(pac_dir, osc.core.store)
        self.assertFalse(os.path.exists(os.path.join(storedir, '_meta_mode')))
        self.assertFalse(os.path.exists(os.path.join(storedir, '_size_limit')))
        self._check_list(os.path.join(storedir, '_project'), 'osctest\n')
        self._check_list(os.path.join(storedir, '_package'), 'testpkg\n')
        self._check_list(os.path.join(storedir, '_files'), '<directory />\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')

    def test_size_limit(self):
        """initialize a package dir with size_limit parameter"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        osc.core.Package.init_package('http://localhost', 'osctest', 'testpkg', pac_dir, size_limit=42)
        storedir = os.path.join(pac_dir, osc.core.store)
        self.assertFalse(os.path.exists(os.path.join(storedir, '_meta_mode')))
        self._check_list(os.path.join(storedir, '_size_limit'), '42\n')
        self._check_list(os.path.join(storedir, '_project'), 'osctest\n')
        self._check_list(os.path.join(storedir, '_package'), 'testpkg\n')
        self._check_list(os.path.join(storedir, '_files'), '<directory />\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')

    def test_meta_mode(self):
        """initialize a package dir with meta paramter"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        osc.core.Package.init_package('http://localhost', 'osctest', 'testpkg', pac_dir, meta=True)
        storedir = os.path.join(pac_dir, osc.core.store)
        self.assertFalse(os.path.exists(os.path.join(storedir, '_size_limit')))
        self._check_list(os.path.join(storedir, '_meta_mode'), '')
        self._check_list(os.path.join(storedir, '_project'), 'osctest\n')
        self._check_list(os.path.join(storedir, '_package'), 'testpkg\n')
        self._check_list(os.path.join(storedir, '_files'), '<directory />\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')

    def test_dirExists(self):
        """initialize a package dir (dir already exists)"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        os.mkdir(pac_dir)
        osc.core.Package.init_package('http://localhost', 'osctest', 'testpkg', pac_dir)
        storedir = os.path.join(pac_dir, osc.core.store)
        self.assertFalse(os.path.exists(os.path.join(storedir, '_meta_mode')))
        self.assertFalse(os.path.exists(os.path.join(storedir, '_size_limit')))
        self._check_list(os.path.join(storedir, '_project'), 'osctest\n')
        self._check_list(os.path.join(storedir, '_package'), 'testpkg\n')
        self._check_list(os.path.join(storedir, '_files'), '<directory />\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')

    def test_storedirExists(self):
        """initialize a package dir (dir+storedir already exists)"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        os.mkdir(pac_dir)
        os.mkdir(os.path.join(pac_dir, osc.core.store))
        self.assertRaises(osc.oscerr.OscIOError, osc.core.Package.init_package, 'http://localhost', 'osctest', 'testpkg', pac_dir)

    def test_dirIsFile(self):
        """initialize a package dir (dir is a file)"""
        pac_dir = os.path.join(self.tmpdir, 'testpkg')
        os.mkdir(pac_dir)
        with open(os.path.join(pac_dir, osc.core.store), 'w') as f:
            f.write('foo\n')
        self.assertRaises(osc.oscerr.OscIOError, osc.core.Package.init_package, 'http://localhost', 'osctest', 'testpkg', pac_dir)


if __name__ == '__main__':
    unittest.main()
