import importlib
import os
import tempfile
import unittest

import osc.conf
import osc.grabber as osc_grabber


class TestMirrorGroup(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='osc_test')
        # reset the global `config` in preparation for running the tests
        importlib.reload(osc.conf)
        osc.conf.get_config()

    def tearDown(self):
        # reset the global `config` to avoid impacting tests from other classes
        importlib.reload(osc.conf)
        try:
            shutil.rmtree(self.tmpdir)
        except:
            pass

    def test_invalid_scheme(self):
        gr = osc_grabber.OscFileGrabber()
        mg = osc_grabber.OscMirrorGroup(gr, ["container://example.com"])
        mg.urlgrab(None, os.path.join(self.tmpdir, "file"))


if __name__ == "__main__":
    unittest.main()
