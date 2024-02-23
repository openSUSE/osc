import textwrap
import unittest

from osc.util.models import *


class TestXmlModel(unittest.TestCase):
    def test_attribute(self):
        class TestModel(XmlModel):
            XML_TAG = "tag"
            value: str = Field(xml_attribute=True)

        m = TestModel(value="FOO")
        self.assertEqual(m.dict(), {"value": "FOO"})
        expected = """<tag value="FOO" />"""
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = TestModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)

    def test_element(self):
        class TestModel(XmlModel):
            XML_TAG = "tag"
            value: str = Field()

        m = TestModel(value="FOO")
        self.assertEqual(m.dict(), {"value": "FOO"})
        expected = textwrap.dedent(
            """
            <tag>
              <value>FOO</value>
            </tag>
            """
        ).strip()
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = TestModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)

    def test_element_list(self):
        class TestModel(XmlModel):
            XML_TAG = "tag"
            value_list: List[str] = Field(xml_name="value")

        m = TestModel(value_list=["FOO", "BAR"])
        self.assertEqual(m.dict(), {"value_list": ["FOO", "BAR"]})
        expected = textwrap.dedent(
            """
            <tag>
              <value>FOO</value>
              <value>BAR</value>
            </tag>
            """
        ).strip()
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = TestModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)

    def test_child_model(self):
        class ChildModel(XmlModel):
            XML_TAG = "child"
            value: str = Field()

        class ParentModel(XmlModel):
            XML_TAG = "parent"
            text: str = Field()
            child: ChildModel = Field()

        m = ParentModel(text="TEXT", child={"value": "FOO"})
        expected = textwrap.dedent(
            """
            <parent>
              <text>TEXT</text>
              <child>
                <value>FOO</value>
              </child>
            </parent>
            """
        ).strip()
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = ParentModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)

    def test_child_model_list(self):
        class ChildModel(XmlModel):
            XML_TAG = "child"
            value: str = Field()

        class ParentModel(XmlModel):
            XML_TAG = "parent"
            text: str = Field()
            child: List[ChildModel] = Field()

        m = ParentModel(text="TEXT", child=[{"value": "FOO"}, {"value": "BAR"}])
        expected = textwrap.dedent(
            """
            <parent>
              <text>TEXT</text>
              <child>
                <value>FOO</value>
              </child>
              <child>
                <value>BAR</value>
              </child>
            </parent>
            """
        ).strip()
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = ParentModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)

    def test_child_model_list_wrapped(self):
        class ChildModel(XmlModel):
            XML_TAG = "child"
            value: str = Field()

        class ParentModel(XmlModel):
            XML_TAG = "parent"
            text: str = Field()
            child: List[ChildModel] = Field(xml_wrapped=True, xml_name="children")

        m = ParentModel(text="TEXT", child=[{"value": "FOO"}, {"value": "BAR"}])
        expected = textwrap.dedent(
            """
            <parent>
              <text>TEXT</text>
              <children>
                <child>
                  <value>FOO</value>
                </child>
                <child>
                  <value>BAR</value>
                </child>
              </children>
            </parent>
            """
        ).strip()
        self.assertEqual(m.to_string(), expected)

        # verify that we can also load the serialized data
        m = ParentModel.from_string(expected)
        self.assertEqual(m.to_string(), expected)


if __name__ == "__main__":
    unittest.main()
