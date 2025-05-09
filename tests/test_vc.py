import os
import unittest

import osc.conf
from osc.core import vc_export_env

from .common import GET
from .common import patch


class TestVC(unittest.TestCase):
    def setUp(self):
        osc.conf.config = osc.conf.Options()

        config = osc.conf.config
        host_options = osc.conf.HostOptions(
            config, apiurl="http://localhost", username="Admin"
        )
        config.api_host_options[host_options["apiurl"]] = host_options
        config["apiurl"] = host_options["apiurl"]
        self.host_options = host_options

    def test_vc_export_env_conf(self):
        self.host_options.realname = "<REALNAME>"
        self.host_options.email = "<EMAIL>"

        with patch.dict(os.environ, {}, clear=True):
            vc_export_env("http://localhost")
            expected = {
                "VC_REALNAME": "<REALNAME>",
                "VC_MAILADDR": "<EMAIL>",
                "mailaddr": "<EMAIL>",
            }
            self.assertEqual(os.environ, expected)

    @GET(
        "http://localhost/person/Admin",
        text="<person><login>Admin</login><email>root@localhost</email><realname>OBS Instance Superuser</realname></person>",
    )
    def test_vc_export_env_conf_realname(self):
        self.host_options.realname = "<REALNAME>"
        with patch.dict(os.environ, {}, clear=True):
            vc_export_env("http://localhost")
            expected = {
                "VC_REALNAME": "<REALNAME>",
                "VC_MAILADDR": "root@localhost",
                "mailaddr": "root@localhost",
            }
            self.assertEqual(os.environ, expected)

    @GET(
        "http://localhost/person/Admin",
        text="<person><login>Admin</login><email>root@localhost</email><realname>OBS Instance Superuser</realname></person>",
    )
    def test_vc_export_env_conf_email(self):
        self.host_options.email = "<EMAIL>"
        with patch.dict(os.environ, {}, clear=True):
            vc_export_env("http://localhost")
            expected = {
                "VC_REALNAME": "OBS Instance Superuser",
                "VC_MAILADDR": "<EMAIL>",
                "mailaddr": "<EMAIL>",
            }
            self.assertEqual(os.environ, expected)

    @GET(
        "http://localhost/person/Admin",
        text="<person><login>Admin</login><email>root@localhost</email><realname>OBS Instance Superuser</realname></person>",
    )
    def test_vc_export_env_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            vc_export_env("http://localhost")
            expected = {
                "VC_REALNAME": "OBS Instance Superuser",
                "VC_MAILADDR": "root@localhost",
                "mailaddr": "root@localhost",
            }
            self.assertEqual(os.environ, expected)


if __name__ == "__main__":
    unittest.main()
