import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest


class TestMaintainershipConverter(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="osc_test_maintainership_converter_")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_file(self, text):
        path = os.path.join(self.tmpdir, "_maintainership.json")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def _run_converter(self, path, in_place=False):
        from osc.commands_git.file_maintainership_migrate import FileMaintainershipMigrateCommand

        cmd = FileMaintainershipMigrateCommand.__new__(FileMaintainershipMigrateCommand)

        args = type("Args", (), {"path": path, "in_place": in_place})()
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            cmd.run(args)
        return stdout.getvalue()

    def test_legacy_format_converted(self):
        """Legacy format is converted to v1.0 format."""
        path = self._write_file(
            '{"":["project-maintainer","@project-group"], "package1":["alice","@pkg1-group"], "package2":["bob"]}'
        )
        output = self._run_converter(path)
        result = json.loads(output)

        self.assertEqual(result["header"]["document"], "obs-maintainers")
        self.assertEqual(result["header"]["version"], "1.0")

        self.assertEqual(result["project"]["users"], ["project-maintainer"])
        self.assertEqual(result["project"]["groups"], ["project-group"])

        self.assertEqual(result["packages"]["package1"]["users"], ["alice"])
        self.assertEqual(result["packages"]["package1"]["groups"], ["pkg1-group"])

        self.assertEqual(result["packages"]["package2"]["users"], ["bob"])
        self.assertIsNone(result["packages"]["package2"]["groups"])

    def test_v1_format_passthrough(self):
        """v1.0 format is printed unchanged."""
        path = self._write_file(
            '{"header":{"document":"obs-maintainers","version":"1.0"},'
            '"project":{"users":["alice"],"groups":null},'
            '"packages":{"pkg1":{"users":["bob"],"groups":["team"]},'
            '"pkg2":{"users":null,"groups":["team"]}}}'
        )
        output = self._run_converter(path)
        result = json.loads(output)

        self.assertEqual(result["header"]["document"], "obs-maintainers")
        self.assertEqual(result["header"]["version"], "1.0")
        self.assertEqual(result["project"]["users"], ["alice"])
        self.assertEqual(result["packages"]["pkg1"]["users"], ["bob"])
        self.assertEqual(result["packages"]["pkg1"]["groups"], ["team"])

    def test_legacy_empty_project_maintainers(self):
        """Legacy format with no project-level maintainers."""
        path = self._write_file('{"package1":["alice"]}')
        output = self._run_converter(path)
        result = json.loads(output)

        self.assertEqual(result["header"]["document"], "obs-maintainers")
        self.assertIsNone(result["project"]["users"])
        self.assertIsNone(result["project"]["groups"])
        self.assertEqual(result["packages"]["package1"]["users"], ["alice"])

    def test_legacy_groups_only(self):
        """Legacy format with only groups, no users."""
        path = self._write_file('{"":["@admins","@maintainers"],"pkg":["@team"]}')
        output = self._run_converter(path)
        result = json.loads(output)

        self.assertIsNone(result["project"]["users"])
        self.assertEqual(result["project"]["groups"], ["admins", "maintainers"])
        self.assertIsNone(result["packages"]["pkg"]["users"])
        self.assertEqual(result["packages"]["pkg"]["groups"], ["team"])

    def test_file_not_found(self):
        """Non-existent file raises an error."""
        path = os.path.join(self.tmpdir, "nonexistent.json")
        with self.assertRaises(FileNotFoundError):
            self._run_converter(path)

    def test_invalid_json(self):
        """Invalid JSON raises an error."""
        path = os.path.join(self.tmpdir, "_maintainership.json")
        with open(path, "w") as f:
            f.write("not valid json")
        with self.assertRaises(json.JSONDecodeError):
            self._run_converter(path)

    def test_in_place(self):
        """With --in-place, result is written back to the file."""
        path = self._write_file('{"":["alice","@group"],"pkg1":["bob"]}')
        output = self._run_converter(path, in_place=True)
        self.assertEqual(output, "")

        with open(path, "r", encoding="utf-8") as f:
            result = json.load(f)

        self.assertEqual(result["header"]["document"], "obs-maintainers")
        self.assertEqual(result["header"]["version"], "1.0")
        self.assertEqual(result["project"]["users"], ["alice"])
        self.assertEqual(result["project"]["groups"], ["group"])
        self.assertEqual(result["packages"]["pkg1"]["users"], ["bob"])


if __name__ == "__main__":
    unittest.main()
