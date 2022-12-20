import os
import shutil
import tempfile
import unittest

from osc.commandline import pop_project_package_from_args
from osc.commandline import pop_project_package_repository_arch_from_args
from osc.commandline import pop_project_package_targetproject_targetpackage_from_args
from osc.commandline import pop_repository_arch_from_args
from osc.oscerr import NoWorkingCopy, OscValueError
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
        self.assertRaises(
            OscValueError,
            pop_project_package_from_args,
            args,
            default_package="default-package",
        )

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
            args,
            default_project="default-project",
            default_package="default-package",
            package_is_optional=True,
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
        self.assertRaises(
            NoWorkingCopy,
            pop_project_package_from_args,
            args,
            default_project=".",
            default_package=".",
        )

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
        project, package = pop_project_package_from_args(
            args, default_project=".", default_package="."
        )
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


class TestPopRepositoryArchFromArgs(unittest.TestCase):
    def test_individial_args(self):
        args = ["repo", "arch", "another-arg"]
        repo, arch = pop_repository_arch_from_args(args)
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, ["another-arg"])

    def test_slash_separator(self):
        args = ["repo/arch", "another-arg"]
        repo, arch = pop_repository_arch_from_args(args)
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, ["another-arg"])

    def test_missing_repository(self):
        args = []
        self.assertRaises(OscValueError, pop_repository_arch_from_args, args)

    def test_missing_arch(self):
        args = ["repo"]
        self.assertRaises(OscValueError, pop_repository_arch_from_args, args)


class TestPopProjectPackageRepositoryArchFromArgs(unittest.TestCase):
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

    def test_individual_args(self):
        args = ["project", "package", "repo", "arch", "another-arg"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, ["another-arg"])

    def test_slash_separator(self):
        args = ["project/package", "repo/arch", "another-arg"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, ["another-arg"])

    def test_missing_arch(self):
        args = ["project", "package", "repo"]
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )

    def test_no_working_copy(self):
        args = ["repo", "arch"]
        self.assertRaises(
            NoWorkingCopy, pop_project_package_repository_arch_from_args, args
        )

    def test_working_copy(self):
        self._write_store("store_project", "store_package")
        args = ["repo", "arch"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")

    def test_working_copy_extra_arg(self):
        self._write_store("store_project", "store_package")
        args = ["repo", "arch", "another-arg"]
        # example of invalid usage, working copy is not used when there's 3+ args; [project, package, ...] are expected
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )


class TestPopProjectPackageTargetProjectTargetPackageFromArgs(unittest.TestCase):
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

    def test_individual_args(self):
        args = ["project", "package", "target-project", "target-package", "another-arg"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, "target-package")
        self.assertEqual(args, ["another-arg"])

    def test_slash_separator(self):
        args = ["project/package", "target-project/target-package", "another-arg"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, "target-package")
        self.assertEqual(args, ["another-arg"])

    def test_missing_target_package(self):
        args = ["project", "package", "target-project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, target_package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_no_working_copy(self):
        args = ["target-project", "target-package"]
        self.assertRaises(
            NoWorkingCopy,
            pop_project_package_targetproject_targetpackage_from_args,
            args,
        )

    def test_working_copy(self):
        self._write_store("store_project", "store_package")
        args = ["target-project", "target-package"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, "target-package")

    def test_working_copy_missing_target_package(self):
        self._write_store("store_project", "store_package")
        args = ["target-project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, target_package_is_optional=True
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, None)

    def test_working_copy_extra_arg(self):
        self._write_store("store_project", "store_package")
        args = ["target-project", "target-package", "another-arg"]
        # example of invalid usage, working copy is not used when there's 3+ args; [project, package, ...] are expected
        self.assertRaises(
            OscValueError,
            pop_project_package_targetproject_targetpackage_from_args,
            args,
        )


if __name__ == "__main__":
    unittest.main()
