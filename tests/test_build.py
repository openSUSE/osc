import unittest

import osc.conf
from osc.build import check_trusted_projects
from osc.oscerr import UserAbort


class TestTrustedProjects(unittest.TestCase):
    def setUp(self):
        osc.conf.config = osc.conf.Options()

    def test_name(self):
        apiurl = "https://example.com"
        osc.conf.config["apiurl"] = apiurl
        host_options = {
            "apiurl": apiurl,
            "username": "user",
            "trusted_prj": [],
        }
        osc.conf.config.setdefault("api_host_options", {})[apiurl] = host_options

        self.assertRaises(UserAbort, check_trusted_projects, apiurl, ["foo"], interactive=False)

        osc.conf.config["api_host_options"][apiurl]["trusted_prj"] = ["qwerty", "foo", "asdfg"]
        check_trusted_projects(apiurl, ["foo"], interactive=False)

    def test_glob(self):
        apiurl = "https://example.com"
        osc.conf.config["apiurl"] = apiurl
        host_options = {
            "apiurl": apiurl,
            "username": "user",
            "trusted_prj": [],
        }
        osc.conf.config.setdefault("api_host_options", {})[apiurl] = host_options

        osc.conf.config["api_host_options"][apiurl]["trusted_prj"] = ["f*"]
        check_trusted_projects(apiurl, ["foo"], interactive=False)


if __name__ == "__main__":
    unittest.main()
