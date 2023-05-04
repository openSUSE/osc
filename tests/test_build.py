import importlib
import unittest

import osc.conf
from osc.build import check_trusted_projects
from osc.oscerr import UserAbort


class TestTrustedProjects(unittest.TestCase):
    def setUp(self):
        # reset the global `config` in preparation for running the tests
        importlib.reload(osc.conf)

    def tearDown(self):
        # reset the global `config` to avoid impacting tests from other classes
        importlib.reload(osc.conf)

    def test_name(self):
        apiurl = "https://example.com"
        osc.conf.config["apiurl"] = apiurl
        osc.conf.config.setdefault("api_host_options", {}).setdefault(apiurl, {}).setdefault("trusted_prj", None)

        osc.conf.config["api_host_options"][apiurl]["trusted_prj"] = []
        self.assertRaises(UserAbort, check_trusted_projects, apiurl, ["foo"], interactive=False)

        osc.conf.config["api_host_options"][apiurl]["trusted_prj"] = ["qwerty", "foo", "asdfg"]
        check_trusted_projects(apiurl, ["foo"], interactive=False)

    def test_glob(self):
        apiurl = "https://example.com"
        osc.conf.config["apiurl"] = apiurl
        osc.conf.config.setdefault("api_host_options", {}).setdefault(apiurl, {}).setdefault("trusted_prj", None)

        osc.conf.config["api_host_options"][apiurl]["trusted_prj"] = ["f*"]
        check_trusted_projects(apiurl, ["foo"], interactive=False)


if __name__ == "__main__":
    unittest.main()
