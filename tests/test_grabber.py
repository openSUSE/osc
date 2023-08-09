import importlib
import os
import tempfile
import unittest

import osc.conf
import osc.grabber as osc_grabber


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "conf_fixtures")


class TestMirrorGroup(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        # reset the global `config` in preparation for running the tests
        importlib.reload(osc.conf)
        oscrc = os.path.join(self._get_fixtures_dir(), "oscrc")
        osc.conf.get_config(override_conffile=oscrc, override_no_keyring=True)

    def tearDown(self):
        # reset the global `config` to avoid impacting tests from other classes
        importlib.reload(osc.conf)
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass

    def _get_fixtures_dir(self):
        return FIXTURES_DIR

    def test_invalid_scheme(self):
        gr = osc_grabber.OscFileGrabber()
        mg = osc_grabber.OscMirrorGroup(gr, ["container://example.com"])
        mg.urlgrab(None, os.path.join(self.tmpdir, "file"))


if __name__ == "__main__":
    unittest.main()
