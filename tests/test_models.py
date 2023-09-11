import unittest
from typing import Set

from osc.util.models import *
from osc.util.models import get_origin


class TestTyping(unittest.TestCase):
    def test_get_origin_list(self):
        typ = get_origin(list)
        self.assertEqual(typ, None)

    def test_get_origin_list_str(self):
        typ = get_origin(List[str])
        self.assertEqual(typ, list)


class TestNotSet(unittest.TestCase):
    def test_repr(self):
        self.assertEqual(repr(NotSet), "NotSet")

    def test_bool(self):
        self.assertEqual(bool(NotSet), False)


class Test(unittest.TestCase):
    def test_modified(self):
        class TestModel(BaseModel):
            a: str = Field(default="default")
            b: Optional[str] = Field(default=None)

        m = TestModel()
        self.assertEqual(m.dict(exclude_unset=True), {"a": "default"})

        m = TestModel(b=None)
        self.assertEqual(m.dict(exclude_unset=True), {"a": "default", "b": None})

    def test_unknown_fields(self):
        class TestModel(BaseModel):
            pass

        self.assertRaises(TypeError, TestModel, does_not_exist=None)

    def test_uninitialized(self):
        class TestModel(BaseModel):
            field: str = Field()

        self.assertRaises(TypeError, TestModel)

    def test_invalid_type(self):
        class TestModel(BaseModel):
            field: Optional[str] = Field()

        m = TestModel()
        self.assertRaises(TypeError, setattr, m.field, [])

    def test_unsupported_type(self):
        class TestModel(BaseModel):
            field: Set[str] = Field(default=None)

        self.assertRaises(TypeError, TestModel)

    def test_is_set(self):
        class TestModel(BaseModel):
            field: Optional[str] = Field()

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_set, False)
        self.assertEqual(m.field, None)
        m.field = "text"
        self.assertEqual(field.is_set, True)
        self.assertEqual(m.field, "text")

    def test_str(self):
        class TestModel(BaseModel):
            field: str = Field(default="default")

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, False)
        self.assertEqual(field.is_set, False)
        self.assertEqual(field.origin_type, str)

        self.assertEqual(m.field, "default")
        m.field = "text"
        self.assertEqual(m.field, "text")

    def test_optional_str(self):
        class TestModel(BaseModel):
            field: Optional[str] = Field()

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, True)
        self.assertEqual(field.is_set, False)
        self.assertEqual(field.origin_type, str)

        self.assertEqual(m.field, None)
        m.field = "text"
        self.assertEqual(m.field, "text")

    def test_int(self):
        class TestModel(BaseModel):
            field: int = Field(default=0)

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, False)
        self.assertEqual(field.origin_type, int)

        self.assertEqual(m.field, 0)
        m.field = 1
        self.assertEqual(m.field, 1)

    def test_optional_int(self):
        class TestModel(BaseModel):
            field: Optional[int] = Field()

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, True)
        self.assertEqual(field.origin_type, int)

        self.assertEqual(m.field, None)
        m.field = 1
        self.assertEqual(m.field, 1)

    def test_submodel(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: TestSubmodel = Field(default={})

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, True)
        self.assertEqual(field.is_optional, False)
        self.assertEqual(field.origin_type, TestSubmodel)

        m = TestModel(field=TestSubmodel())
        self.assertEqual(m.field.text, "default")

        m = TestModel(field={"text": "text"})
        self.assertEqual(m.field.text, "text")

    def test_optional_submodel(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: Optional[TestSubmodel] = Field(default=None)

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, True)
        self.assertEqual(field.is_optional, True)
        self.assertEqual(field.origin_type, TestSubmodel)
        self.assertEqual(m.field, None)

        m = TestModel(field=TestSubmodel())
        self.assertIsInstance(m.field, TestSubmodel)
        self.assertEqual(m.field.text, "default")

        m = TestModel(field={"text": "text"})
        self.assertNotEqual(m.field, None)
        self.assertEqual(m.field.text, "text")

    def test_parent(self):
        class ParentModel(BaseModel):
            field: str = Field(default="text")

        class ChildModel(BaseModel):
            field: str = Field(default=FromParent("field"))
            field2: str = Field(default=FromParent("field"))

        p = ParentModel()
        c = ChildModel(_parent=p)
        self.assertEqual(p.field, "text")
        self.assertEqual(c.field, "text")
        self.assertEqual(c.field2, "text")

        c.field = "new-text"
        self.assertEqual(p.field, "text")
        self.assertEqual(c.field, "new-text")
        self.assertEqual(c.field2, "text")


if __name__ == "__main__":
    unittest.main()
