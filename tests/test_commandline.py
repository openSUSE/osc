import os
import shutil
import tempfile
import unittest

from osc.commandline import pop_project_package_from_args
from osc.oscerr import NoWorkingCopy
from osc.store import Store


class TestPopProjectPackageFromArgs(unittest.TestCase):
    def _write_store(self, project=None, package=None):
        store = Store(self.tmpdir, check=False)
        if project:
            store.project = project
            store.is_project = True
        if package:
            store.package = package
            store.is_project = False
            store.is_package = True

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test")
        os.chdir(self.tmpdir)

    def tearDown(self):
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def test_explicit_project_and_package(self):
        args = ["project", "package", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(args, ["another-arg"])

    def test_defaults(self):
        args = ["project"]
        project, package = pop_project_package_from_args(args, default_package="default-package")
        self.assertEqual(project, "project")
        self.assertEqual(package, "default-package")
        self.assertEqual(args, [])

        args = ["project"]
        project, package = pop_project_package_from_args(
            args, default_package="default-package", package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "default-package")
        self.assertEqual(args, [])

        args = []
        project, package = pop_project_package_from_args(
            args, default_project="default-project", default_package="default-package"
        )
        self.assertEqual(project, "default-project")
        self.assertEqual(package, "default-package")
        self.assertEqual(args, [])

        args = []
        project, package = pop_project_package_from_args(
            args, default_project="default-project", default_package="default-package", package_is_optional=True
        )
        self.assertEqual(project, "default-project")
        self.assertEqual(package, "default-package")
        self.assertEqual(args, [])

    def test_slash_separator(self):
        args = ["project/package", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(args, ["another-arg"])

        args = ["project/", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "project")
        self.assertEqual(package, "")
        self.assertEqual(args, ["another-arg"])

    def test_no_working_copy(self):
        args = [".", "."]
        self.assertRaises(NoWorkingCopy, pop_project_package_from_args, args)

        args = [".", "package"]
        self.assertRaises(NoWorkingCopy, pop_project_package_from_args, args)

        args = ["project", "."]
        self.assertRaises(NoWorkingCopy, pop_project_package_from_args, args)

    def test_project_and_package_from_project_working_copy(self):
        self._write_store("store_project")

        args = [".", ".", "another-arg"]
        self.assertRaises(NoWorkingCopy, pop_project_package_from_args, args)

        args = ["."]
        project, package = pop_project_package_from_args(args, package_is_optional=True)
        self.assertEqual(project, "store_project")
        self.assertEqual(package, None)
        self.assertEqual(args, [])

        args = []
        self.assertRaises(NoWorkingCopy, pop_project_package_from_args, args, default_project=".", default_package=".")

        args = []
        project, package = pop_project_package_from_args(
            args, default_project=".", default_package=".", package_is_optional=True
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, None)
        self.assertEqual(args, [])

    def test_project_and_package_from_package_working_copy(self):
        self._write_store("store_project", "store_package")

        args = [".", ".", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(args, ["another-arg"])

        args = ["."]
        project, package = pop_project_package_from_args(args, package_is_optional=True)
        self.assertEqual(project, "store_project")
        self.assertEqual(package, None)
        self.assertEqual(args, [])

        args = []
        project, package = pop_project_package_from_args(args, default_project=".", default_package=".")
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(args, [])

        args = []
        project, package = pop_project_package_from_args(
            args, default_project=".", default_package=".", package_is_optional=True
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(args, [])


if __name__ == "__main__":
    unittest.main()
