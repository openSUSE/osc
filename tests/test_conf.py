import importlib
import unittest

import osc.conf


class TestConf(unittest.TestCase):
    def setUp(self):
        # reset the global `config` in preparation for running the tests
        importlib.reload(osc.conf)

    def tearDown(self):
        # reset the global `config` to avoid impacting tests from other classes
        importlib.reload(osc.conf)

    def test_bool_opts_defaults(self):
        opts = osc.conf.boolean_opts
        config = osc.conf.config
        for opt in opts:
            self.assertIsInstance(config[opt], bool, msg=f"option: '{opt}'")

    def test_int_opts_defaults(self):
        opts = osc.conf.integer_opts
        config = osc.conf.config
        for opt in opts:
            self.assertIsInstance(config[opt], int, msg=f"option: '{opt}'")

    def test_bool_opts(self):
        osc.conf.get_config()
        opts = osc.conf.boolean_opts
        config = osc.conf.config
        for opt in opts:
            self.assertIsInstance(config[opt], bool, msg=f"option: '{opt}'")

    def test_int_opts(self):
        osc.conf.get_config()
        opts = osc.conf.integer_opts
        config = osc.conf.config
        for opt in opts:
            self.assertIsInstance(config[opt], int, msg=f"option: '{opt}'")


if __name__ == "__main__":
    unittest.main()
