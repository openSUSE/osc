import os
import unittest

import osc.core
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'project_package_status_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestProjectStatus)


class TestProjectStatus(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def test_simple(self):
        """get the status of a package with state ' '"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = ' '
        st = prj.status('simple')
        self.assertEqual(exp_st, st)

    def test_added(self):
        """get the status of an added package"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = 'A'
        st = prj.status('added')
        self.assertEqual(exp_st, st)

    def test_deleted(self):
        """get the status of a deleted package"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = 'D'
        st = prj.status('deleted')
        self.assertEqual(exp_st, st)

    def test_added_deleted(self):
        """
        get the status of a package which was added and deleted
        afterwards (with a non osc command)
        """
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = '!'
        st = prj.status('added_deleted')
        self.assertEqual(exp_st, st)

    def test_missing(self):
        """
        get the status of a package with state " "
        which was removed by a non osc command
        """
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = '!'
        st = prj.status('missing')
        self.assertEqual(exp_st, st)

    def test_deleted_deleted(self):
        """
        get the status of a package which was deleted (with an
        osc command) and afterwards the package directory was
        deleted with a non osc command
        """
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = 'D'
        st = prj.status('deleted_deleted')
        self.assertEqual(exp_st, st)

    def test_unversioned_exists(self):
        """get the status of an unversioned package"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = '?'
        st = prj.status('excluded')
        self.assertEqual(exp_st, st)

    def test_unversioned_nonexistent(self):
        """get the status of an unversioned, nonexistent package"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        self.assertRaises(osc.oscerr.OscIOError, prj.status, 'doesnotexist')

    def test_get_status(self):
        """get the status of the complete project"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = [(' ', 'conflict'), (' ', 'simple'), ('A', 'added'), ('D', 'deleted'),
                  ('!', 'missing'), ('!', 'added_deleted'), ('D', 'deleted_deleted'), ('?', 'excluded')]
        st = prj.get_status()
        self.assertEqual(exp_st, st)

    def test_get_status_excl(self):
        """get the status of the complete project (exclude some states)"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        exp_st = [('A', 'added'), ('!', 'missing'), ('!', 'added_deleted')]
        st = prj.get_status('D', ' ', '?')
        self.assertEqual(exp_st, st)

    def test_get_pacobj_simple(self):
        """package exists"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('simple')
        self.assertTrue(isinstance(p, osc.core.Package))
        self.assertEqual(p.name, 'simple')

    def test_get_pacobj_added(self):
        """package has state 'A', also test pac_kwargs"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('added', progress_obj={})
        self.assertTrue(isinstance(p, osc.core.Package))
        self.assertEqual(p.name, 'added')
        self.assertEqual(p.progress_obj, {})

    def test_get_pacobj_deleted(self):
        """package has state 'D' and exists, also test pac_args"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('deleted', {})
        self.assertTrue(isinstance(p, osc.core.Package))
        self.assertEqual(p.name, 'deleted')
        self.assertEqual(p.progress_obj, {})

    def test_get_pacobj_missing(self):
        """package is missing"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('missing')
        self.assertTrue(isinstance(p, type(None)))

    def test_get_pacobj_deleted_deleted(self):
        """package has state 'D' and does not exist"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('deleted_deleted')
        self.assertTrue(isinstance(p, type(None)))

    def test_get_pacobj_unversioned(self):
        """package/dir has state '?'"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('excluded')
        self.assertTrue(isinstance(p, type(None)))

    def test_get_pacobj_nonexistent(self):
        """package/dir does not exist"""
        self._change_to_pkg('.')
        prj = osc.core.Project('.', getPackageList=False)
        p = prj.get_pacobj('doesnotexist')
        self.assertTrue(isinstance(p, type(None)))


if __name__ == '__main__':
    unittest.main()
