import os
import unittest

import osc.conf
import osc.core
import osc.oscerr

from .common import GET, OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'init_project_fixtures')


def suite():
    return unittest.defaultTestLoader.loadTestsFromTestCase(TestInitProject)


class TestInitProject(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def setUp(self):
        super().setUp(copytree=False)

    def test_simple(self):
        """initialize a project dir"""
        prj_dir = os.path.join(self.tmpdir, 'testprj')
        prj = osc.core.Project.init_project('http://localhost', prj_dir, 'testprj', getPackageList=False)
        self.assertTrue(isinstance(prj, osc.core.Project))
        storedir = os.path.join(prj_dir, osc.core.store)
        self._check_list(os.path.join(storedir, '_project'), 'testprj\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')
        self._check_list(os.path.join(storedir, '_packages'), '<project name="testprj" />')

    def test_dirExists(self):
        """initialize a project dir but the dir already exists"""
        prj_dir = os.path.join(self.tmpdir, 'testprj')
        os.mkdir(prj_dir)
        prj = osc.core.Project.init_project('http://localhost', prj_dir, 'testprj', getPackageList=False)
        self.assertTrue(isinstance(prj, osc.core.Project))
        storedir = os.path.join(prj_dir, osc.core.store)
        self._check_list(os.path.join(storedir, '_project'), 'testprj\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')
        self._check_list(os.path.join(storedir, '_packages'), '<project name="testprj" />')

    def test_storedirExists(self):
        """initialize a project dir but the storedir already exists"""
        prj_dir = os.path.join(self.tmpdir, 'testprj')
        os.mkdir(prj_dir)
        os.mkdir(os.path.join(prj_dir, osc.core.store))
        self.assertRaises(osc.oscerr.OscIOError, osc.core.Project.init_project, 'http://localhost', prj_dir, 'testprj')

    @GET('http://localhost/source/testprj', text='<directory count="0" />')
    def test_no_package_tracking(self):
        """initialize a project dir but disable package tracking; enable getPackageList=True;
        disable wc_check (because we didn't disable the package tracking before the Project class
        was imported therefore REQ_STOREFILES contains '_packages')
        """
        # disable package tracking
        osc.conf.config['do_package_tracking'] = False
        prj_dir = os.path.join(self.tmpdir, 'testprj')
        os.mkdir(prj_dir)
        prj = osc.core.Project.init_project('http://localhost', prj_dir, 'testprj', False, wc_check=False)
        self.assertTrue(isinstance(prj, osc.core.Project))
        storedir = os.path.join(prj_dir, osc.core.store)
        self._check_list(os.path.join(storedir, '_project'), 'testprj\n')
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')
        self.assertFalse(os.path.exists(os.path.join(storedir, '_packages')))

    @GET('http://localhost/source/testprj/testpkg/_meta', text='<package name="testpkg" project="testprj" />')
    def test_apiurl_mismatch(self):
        """checkout_package into an existing project dir with a different apiurl raises OscIOError"""
        # mock api2 in config to trigger the test connection mock
        osc.conf.config['api_host_options']['http://api2'] = osc.conf.config['api_host_options']['http://localhost']
        prj_dir = os.path.join(self.tmpdir, 'testprj')
        # initialize a project dir with http://localhost
        osc.core.Project.init_project('http://localhost', prj_dir, 'testprj', getPackageList=False)

        # attempt to check out a package from http://api2 into the same project dir
        with self.assertRaises(osc.oscerr.OscIOError) as cm:
            osc.core.checkout_package('http://api2', 'testprj', 'testpkg', prj_dir=prj_dir)
        self.assertRegex(cm.exception.msg, r"The project working copy '.*' uses a different API URL: http://localhost")

        # verify that the project's stored API URL remains unchanged
        storedir = os.path.join(prj_dir, osc.core.store)
        self._check_list(os.path.join(storedir, '_apiurl'), 'http://localhost\n')

        # verify that package tracking remains unchanged (testpkg not added)
        self._check_list(os.path.join(storedir, '_packages'), '<project name="testprj" />')

        # verify that no unintended package working copy was created
        self.assertFalse(os.path.exists(os.path.join(prj_dir, 'testpkg')))


    def test_delete_dir_robustness(self):
        """delete_dir successfully ignores FileNotFoundError during recursive deletion"""
        import tempfile
        import shutil
        from osc.core import delete_dir

        temp_dir = tempfile.mkdtemp(dir=self.tmpdir)
        try:
            # create a file inside temp_dir
            file_path = os.path.join(temp_dir, "somefile")
            with open(file_path, "w") as f:
                f.write("content")

            # mock os.unlink to raise FileNotFoundError on call to simulate concurrent deletion
            original_unlink = os.unlink
            def mocked_unlink(path):
                if os.path.exists(path):
                    original_unlink(path)
                # This call will raise FileNotFoundError
                original_unlink(path)

            from unittest.mock import patch
            with patch("os.unlink", mocked_unlink):
                # this should not raise FileNotFoundError because delete_dir handles it gracefully
                delete_dir(temp_dir)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
