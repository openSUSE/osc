import argparse
import os
import shutil
import tempfile
import unittest

from osc.commandline import Command
from osc.commandline import MainCommand
from osc.commandline import OscMainCommand
from osc.commandline import pop_project_package_from_args
from osc.commandline import pop_project_package_repository_arch_from_args
from osc.commandline import pop_project_package_targetproject_targetpackage_from_args
from osc.commandline import pop_repository_arch_from_args
from osc.oscerr import NoWorkingCopy, OscValueError
from osc.store import Store


class TestMainCommand(MainCommand):
    name = "osc-test"

    def init_arguments(self, command=None):
        self.add_argument(
            "-A",
            "--apiurl",
        )


class TestCommand(Command):
    name = "test-cmd"


OSCRC_LOCALHOST = """
[general]
apiurl = https://localhost

[https://localhost]
user=Admin
pass=opensuse
""".lstrip()


class TestCommandClasses(unittest.TestCase):
    def setUp(self):
        os.environ.pop("OSC_CONFIG", None)
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test")
        os.chdir(self.tmpdir)
        self.oscrc = None

    def tearDown(self):
        os.environ.pop("OSC_CONFIG", None)
        try:
            shutil.rmtree(self.tmpdir)
        except OSError:
            pass

    def write_oscrc_localhost(self):
        self.oscrc = os.path.join(self.tmpdir, "oscrc")
        with open(self.oscrc, "w") as f:
            f.write(OSCRC_LOCALHOST)

    def test_load_commands(self):
        main = TestMainCommand()
        main.load_commands()

    def test_load_command(self):
        main = TestMainCommand()
        cmd = main.load_command(TestCommand, "test.osc.commands")
        self.assertTrue(str(cmd).startswith("<osc plugin test.osc.commands.TestCommand"))

    def test_parent(self):
        class Parent(TestCommand):
            name = "parent"

        class Child(TestCommand):
            name = "child"
            parent = "Parent"

        main = TestMainCommand()
        main.load_command(Parent, "test.osc.commands")
        main.load_command(Child, "test.osc.commands")

        main.parse_args(["parent", "child"])

    def test_invalid_parent(self):
        class Parent(TestCommand):
            name = "parent"

        class Child(TestCommand):
            name = "child"
            parent = "DoesNotExist"

        main = TestMainCommand()
        main.load_command(Parent, "test.osc.commands")
        main.load_command(Child, "test.osc.commands")

    def test_load_twice(self):
        class AnotherCommand(TestCommand):
            name = "another-command"
            aliases = ["test-cmd"]

        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")

        # conflict between names
        self.assertRaises(argparse.ArgumentError, main.load_command, TestCommand, "test.osc.commands")

        # conflict between a name and an alias
        self.assertRaises(argparse.ArgumentError, main.load_command, AnotherCommand, "test.osc.commands")

    def test_intermixing(self):
        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")

        args = main.parse_args(["test-cmd", "--apiurl", "https://example.com"])
        self.assertEqual(args.apiurl, "https://example.com")

        args = main.parse_args(["--apiurl", "https://example.com", "test-cmd"])
        self.assertEqual(args.apiurl, "https://example.com")

    def test_unknown_options(self):
        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")

        args = main.parse_args(["test-cmd", "unknown-arg"])
        self.assertEqual(args.positional_args, ["unknown-arg"])

        self.assertRaises(SystemExit, main.parse_args, ["test-cmd", "--unknown-option"])

    def test_default_apiurl(self):
        class TestMainCommand(OscMainCommand):
            name = "osc-test"

        main = TestMainCommand()
        main.load_command(TestCommand, "test.osc.commands")

        self.write_oscrc_localhost()
        os.environ["OSC_CONFIG"] = self.oscrc
        args = main.parse_args(["test-cmd"])
        main.post_parse_args(args)
        self.assertEqual(args.apiurl, "https://localhost")


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

    def test_individual_args(self):
        args = ["project", "package", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(args, ["another-arg"])

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

        args = ["/", "another-arg"]
        project, package = pop_project_package_from_args(args)
        self.assertEqual(project, "")
        self.assertEqual(package, "")
        self.assertEqual(args, ["another-arg"])

    def test_missing_project(self):
        args = []
        self.assertRaises(
            OscValueError,
            pop_project_package_from_args,
            args,
        )

    def test_optional_project(self):
        args = []
        project, package = pop_project_package_from_args(
            args, project_is_optional=True,
        )
        self.assertEqual(project, None)
        self.assertEqual(package, None)
        self.assertEqual(args, [])

    def test_default_project(self):
        args = []
        project, package = pop_project_package_from_args(
            args, default_project="default-project", package_is_optional=True
        )
        self.assertEqual(project, "default-project")
        self.assertEqual(package, None)
        self.assertEqual(args, [])

    def test_missing_package(self):
        args = ["project"]
        self.assertRaises(
            OscValueError,
            pop_project_package_from_args,
            args,
        )

    def test_optional_package(self):
        args = ["project"]
        project, package = pop_project_package_from_args(
            args, package_is_optional=True,
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, None)
        self.assertEqual(args, [])

    def test_default_package(self):
        args = ["project"]
        project, package = pop_project_package_from_args(
            args, package_is_optional=True, default_package="default-package",
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "default-package")
        self.assertEqual(args, [])

    def test_default_project_package(self):
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

    def test_project_requires_to_specify_package(self):
        args = ["project"]
        self.assertRaises(
            OscValueError,
            pop_project_package_from_args,
            args,
            default_project=".",
            default_package=".",
        )

        # The project from store is ignored because we've specified one.
        # Specifying a package is expected.
        self._write_store("store_project")
        args = ["project"]
        self.assertRaises(
            OscValueError,
            pop_project_package_from_args,
            args,
            default_project=".",
            default_package=".",
        )


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

        args = ["repo/", "another-arg"]
        repo, arch = pop_repository_arch_from_args(args)
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "")
        self.assertEqual(args, ["another-arg"])

        args = ["/", "another-arg"]
        repo, arch = pop_repository_arch_from_args(args)
        self.assertEqual(repo, "")
        self.assertEqual(arch, "")
        self.assertEqual(args, ["another-arg"])

    def test_missing_repository(self):
        args = []
        self.assertRaises(OscValueError, pop_repository_arch_from_args, args)

    def test_optional_repository(self):
        args = []
        repo, arch = pop_repository_arch_from_args(args, repository_is_optional=True)
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_repository(self):
        args = []
        repo, arch = pop_repository_arch_from_args(args, default_repository="repo", arch_is_optional=True)
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_missing_arch(self):
        args = ["repo"]
        self.assertRaises(OscValueError, pop_repository_arch_from_args, args)

    def test_optional_arch(self):
        args = ["repo"]
        repo, arch = pop_repository_arch_from_args(args, arch_is_optional=True)
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_arch(self):
        args = ["repo"]
        repo, arch = pop_repository_arch_from_args(args, default_arch="arch")
        self.assertEqual(repo, "repo")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, [])


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

    def test_missing_project(self):
        args = []
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )

    def test_optional_project(self):
        args = []
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, project_is_optional=True
        )
        self.assertEqual(project, None)
        self.assertEqual(package, None)
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_project(self):
        args = []
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, default_project="project", package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, None)
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_missing_package(self):
        args = ["project"]
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )

    def test_optional_package(self):
        args = ["project"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, None)
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_package(self):
        args = ["project"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, default_package="package", repository_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_missing_repository(self):
        args = ["project", "package"]
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )

    def test_optional_repository(self):
        args = ["project", "package"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, repository_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, None)
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_repository(self):
        args = ["project", "package"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, default_repository="repository", arch_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, "repository")
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_missing_arch(self):
        args = ["project", "package", "repo"]
        self.assertRaises(
            OscValueError, pop_project_package_repository_arch_from_args, args
        )

    def test_optional_arch(self):
        args = ["project", "package", "repository"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, arch_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, "repository")
        self.assertEqual(arch, None)
        self.assertEqual(args, [])

    def test_default_arch(self):
        args = ["project", "package", "repository"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args, default_arch="arch"
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(repo, "repository")
        self.assertEqual(arch, "arch")
        self.assertEqual(args, [])

    def test_no_working_copy(self):
        args = ["repo", "arch"]
        self.assertRaises(
            NoWorkingCopy,
            pop_project_package_repository_arch_from_args,
            args,
            default_project=".",
            default_package=".",
        )

    def test_working_copy(self):
        self._write_store("store_project", "store_package")
        args = ["repo", "arch"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args,
            default_project=".",
            default_package=".",
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
            OscValueError,
            pop_project_package_repository_arch_from_args,
            args,
            default_project=".",
            default_package=".",
        )

    def test_working_copy_optional_arch(self):
        self._write_store("store_project", "store_package")
        args = ["repository"]
        project, package, repo, arch = pop_project_package_repository_arch_from_args(
            args,
            default_project=".",
            default_package=".",
            arch_is_optional=True,
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(repo, "repository")
        self.assertEqual(arch, None)


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

    def test_missing_project(self):
        args = []
        self.assertRaises(
            OscValueError, pop_project_package_targetproject_targetpackage_from_args, args
        )

    def test_optional_project(self):
        args = []
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, project_is_optional=True
        )
        self.assertEqual(project, None)
        self.assertEqual(package, None)
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_default_project(self):
        args = []
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, default_project="project", package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, None)
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_missing_package(self):
        args = ["project"]
        self.assertRaises(
            OscValueError, pop_project_package_targetproject_targetpackage_from_args, args
        )

    def test_optional_package(self):
        args = ["project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, None)
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_default_package(self):
        args = ["project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, default_package="package", target_project_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_missing_target_project(self):
        args = ["project", "package"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, target_project_is_optional=True, target_package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_optional_target_project(self):
        args = ["project", "package"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, target_project_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, None)
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_default_target_project(self):
        args = ["project", "package"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, default_target_project="package", target_package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "package")
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

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

    def test_optional_target_package(self):
        args = ["project", "package", "target-project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, target_package_is_optional=True
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, None)
        self.assertEqual(args, [])

    def test_default_target_package(self):
        args = ["project", "package", "target-project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args, default_target_package="target-package"
        )
        self.assertEqual(project, "project")
        self.assertEqual(package, "package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, "target-package")
        self.assertEqual(args, [])

    def test_no_working_copy(self):
        args = ["target-project", "target-package"]
        self.assertRaises(
            NoWorkingCopy,
            pop_project_package_targetproject_targetpackage_from_args,
            args,
            default_project=".",
            default_package=".",
        )

    def test_working_copy(self):
        self._write_store("store_project", "store_package")
        args = ["target-project", "target-package"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args,
            default_project=".",
            default_package=".",
        )
        self.assertEqual(project, "store_project")
        self.assertEqual(package, "store_package")
        self.assertEqual(target_project, "target-project")
        self.assertEqual(target_package, "target-package")

    def test_working_copy_missing_target_package(self):
        self._write_store("store_project", "store_package")
        args = ["target-project"]
        project, package, target_project, target_package = pop_project_package_targetproject_targetpackage_from_args(
            args,
            default_project=".",
            default_package=".",
            target_package_is_optional=True,
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
