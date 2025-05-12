import io
import unittest

import osc.util.yaml as osc_yaml


YAML = """
dict:
  minus-two: -2
  one: 1
float: 1.2
int: 123
list:
- one
- two
- three
str: text
""".lstrip()


DATA = {
    "list": ["one", "two", "three"],
    "dict": {
        "one": 1,
        "minus-two": -2,
    },
    "str": "text",
    "int": 123,
    "float": 1.2,
}


@unittest.skipIf(not osc_yaml.RUAMEL_YAML, "ruamel.yaml not available")
class TestRuamelYaml(unittest.TestCase):
    def test_dump(self):
        with io.StringIO() as f:
            osc_yaml._ruamel_yaml_dump(DATA, f)
            f.seek(0)
            actual = f.read()
        self.assertEqual(YAML, actual)

    def test_dumps(self):
        actual = osc_yaml._ruamel_yaml_dumps(DATA)
        self.assertEqual(YAML, actual)

    def test_load(self):
        with io.StringIO() as f:
            f.write(YAML)
            f.seek(0)
            actual = osc_yaml._ruamel_yaml_load(f)
        self.assertEqual(DATA, actual)

    def test_loads(self):
        actual = osc_yaml._ruamel_yaml_loads(YAML)
        self.assertEqual(DATA, actual)


@unittest.skipIf(not osc_yaml.PYYAML, "PyYAML not available")
class TestPyYaml(unittest.TestCase):
    def test_dump(self):
        with io.StringIO() as f:
            osc_yaml._pyyaml_dump(DATA, f)
            f.seek(0)
            actual = f.read()
        self.assertEqual(YAML, actual)

    def test_dumps(self):
        actual = osc_yaml._pyyaml_dumps(DATA)
        self.assertEqual(YAML, actual)

    def test_load(self):
        with io.StringIO() as f:
            f.write(YAML)
            f.seek(0)
            actual = osc_yaml._pyyaml_load(f)
        self.assertEqual(DATA, actual)

    def test_loads(self):
        actual = osc_yaml._pyyaml_loads(YAML)
        self.assertEqual(DATA, actual)


if __name__ == "__main__":
    unittest.main()
