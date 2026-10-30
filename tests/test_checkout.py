import os
import unittest

import osc.commandline
import osc.oscerr

from .common import OscTestCase


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "init_project_fixtures")


class TestCheckout(OscTestCase):
    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def setUp(self):
        super().setUp(copytree=False)
        os.chdir(self.tmpdir)

    def test_revision_without_package(self):
        """a revision applies to a package; a project checkout with one is rejected instead of crashing"""
        with self.assertRaises(osc.oscerr.WrongOptions):
            self._run_osc("checkout", "-r", "9", "openSUSE:Tools")


if __name__ == "__main__":
    unittest.main()
