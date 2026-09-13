import unittest

from osc import oscerr


class TestOscErr(unittest.TestCase):
    def test_base_error_str(self):
        self.assertEqual(str(oscerr.OscBaseError(("foo", "bar"))), "foobar")

    def test_config_error_str(self):
        err = oscerr.ConfigError("bad apiurl", "/etc/osc.conf")
        self.assertEqual(str(err), "Error in config file /etc/osc.conf\n   bad apiurl")

    def test_api_error_str(self):
        self.assertEqual(str(oscerr.APIError("not found")), "APIError: not found")

    def test_no_configfile_str(self):
        err = oscerr.NoConfigfile("/etc/osc.conf", "no such file")
        self.assertEqual(str(err), "Config file cannot be found: /etc/osc.conf\n   no such file")

    def test_working_copy_outdated_str(self):
        err = oscerr.WorkingCopyOutdated(("./pkg", 1, 2))
        self.assertEqual(
            str(err),
            "Working copy './pkg' is out of date (rev 1 vs rev 2).\n"
            "Looks as if you need to update it first.",
        )

    def test_project_error_str_without_msg(self):
        self.assertEqual(str(oscerr.ProjectError("myproject")), "ProjectError: myproject")

    def test_project_error_str_with_msg(self):
        err = oscerr.ProjectError("myproject", "does not exist")
        self.assertEqual(str(err), "ProjectError: myproject: does not exist")

    def test_package_error_str_without_msg(self):
        err = oscerr.PackageError("myproject", "mypackage")
        self.assertEqual(str(err), "PackageError: myproject/mypackage")

    def test_package_error_str_with_msg(self):
        err = oscerr.PackageError("myproject", "mypackage", "does not exist")
        self.assertEqual(str(err), "PackageError: myproject/mypackage: does not exist")
