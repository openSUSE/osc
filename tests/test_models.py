import sys
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
    @unittest.skipIf(sys.version_info[:2] < (3, 10), "added in python 3.10")
    def test_union_or(self):
        class TestModel(BaseModel):
            text: str | None = Field()

        m = TestModel()
        self.assertEqual(m.dict(), {"text": None})

        self.assertRaises(TypeError, setattr, m.text, 123)

    def test_dict(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            a: str = Field(default="default")
            b: Optional[str] = Field(default=None)
            sub: Optional[List[TestSubmodel]] = Field(default=None)

        m = TestModel()
        self.assertEqual(m.dict(), {"a": "default", "b": None, "sub": None})

        m.b = "B"
        m.sub = [{"text": "one"}, {"text": "two"}]
        self.assertEqual(m.dict(), {"a": "default", "b": "B", "sub": [{"text": "one"}, {"text": "two"}]})

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

    def test_lazy_default(self):
        class TestModel(BaseModel):
            field: List[str] = Field(default=lambda: ["string"])

        m = TestModel()
        self.assertEqual(m.field, ["string"])

    def test_lazy_default_invalid_type(self):
        class TestModel(BaseModel):
            field: List[str] = Field(default=lambda: None)

        self.assertRaises(TypeError, TestModel)

    def test_is_set(self):
        class TestModel(BaseModel):
            field: Optional[str] = Field()

        m = TestModel()

        self.assertNotIn("field", m._values)
        self.assertEqual(m.field, None)

        m.field = "text"

        self.assertIn("field", m._values)
        self.assertEqual(m.field, "text")

    def test_str(self):
        class TestModel(BaseModel):
            field: str = Field(default="default")

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, False)
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
        m.dict()

        m = TestModel(field=TestSubmodel())
        self.assertIsInstance(m.field, TestSubmodel)
        self.assertEqual(m.field.text, "default")
        m.dict()

        m = TestModel(field={"text": "text"})
        self.assertNotEqual(m.field, None)
        self.assertEqual(m.field.text, "text")
        m.dict()

    def test_list_submodels(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: List[TestSubmodel] = Field(default=[])

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_model_list, True)
        self.assertEqual(field.is_optional, False)
        self.assertEqual(field.origin_type, list)
        m.dict()

        m = TestModel(field=[TestSubmodel()])
        self.assertEqual(m.field[0].text, "default")
        m.dict()

        m = TestModel(field=[{"text": "text"}])
        self.assertEqual(m.field[0].text, "text")
        m.dict()

        self.assertRaises(TypeError, getattr(m, "field"))

    def test_optional_list_submodels(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: Optional[List[TestSubmodel]] = Field(default=[])

        m = TestModel()

        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_model_list, True)
        self.assertEqual(field.is_optional, True)
        self.assertEqual(field.origin_type, list)
        m.dict()

        m = TestModel(field=[TestSubmodel()])
        self.assertEqual(m.field[0].text, "default")
        m.dict()

        m = TestModel(field=[{"text": "text"}])
        self.assertEqual(m.field[0].text, "text")
        m.dict()

        m.field = None
        self.assertEqual(m.field, None)
        m.dict()

    def test_enum(self):
        class Numbers(Enum):
            one = "one"
            two = "two"

        class TestModel(BaseModel):
            field: Optional[Numbers] = Field(default=None)

        m = TestModel()
        field = m.__fields__["field"]
        self.assertEqual(field.is_model, False)
        self.assertEqual(field.is_optional, True)
        self.assertEqual(field.origin_type, Numbers)
        self.assertEqual(m.field, None)

        m.field = "one"
        self.assertEqual(m.field, "one")

        self.assertRaises(ValueError, setattr, m, "field", "does-not-exist")

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

    def test_parent_fallback(self):
        class SubModel(BaseModel):
            field: str = Field(default=FromParent("field", fallback="submodel-fallback"))

        class Model(BaseModel):
            field: str = Field(default=FromParent("field", fallback="model-fallback"))
            sub: Optional[SubModel] = Field()
            sub_list: Optional[List[SubModel]] = Field()

        m = Model()
        s = SubModel(_parent=m)
        m.sub = s
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub.field, "model-fallback")

        m = Model(sub={})
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub.field, "model-fallback")

        m = Model(sub=SubModel())
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub.field, "model-fallback")

        m = Model()
        s = SubModel(_parent=m)
        m.sub_list = [s]
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub_list[0].field, "model-fallback")

        m = Model(sub_list=[{}])
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub_list[0].field, "model-fallback")

        m = Model(sub_list=[SubModel()])
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub_list[0].field, "model-fallback")

        m = Model()
        m.sub_list = []
        m.sub_list.append({})
        self.assertEqual(m.field, "model-fallback")
        self.assertEqual(m.sub_list[0].field, "model-fallback")

    def test_get_callback(self):
        class Model(BaseModel):
            quiet: bool = Field(
                default=False,
            )
            verbose: bool = Field(
                default=False,
                # return False if ``quiet`` is True; return the actual value otherwise
                get_callback=lambda obj, value: False if obj.quiet else value,
            )

        m = Model()
        self.assertEqual(m.quiet, False)
        self.assertEqual(m.verbose, False)

        m.quiet = True
        m.verbose = True
        self.assertEqual(m.quiet, True)
        self.assertEqual(m.verbose, False)

        m.quiet = False
        m.verbose = True
        self.assertEqual(m.quiet, False)
        self.assertEqual(m.verbose, True)

    def test_has_changed(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: Optional[List[TestSubmodel]] = Field(default=[])

        m = TestModel()
        self.assertFalse(m.has_changed())

        # a new instance of empty list
        m.field = []
        self.assertFalse(m.has_changed())

        m.field = [{"text": "one"}, {"text": "two"}]
        self.assertTrue(m.has_changed())

        m.do_snapshot()

        # a new instance of list with new instances of objects with the same data
        m.field = [{"text": "one"}, {"text": "two"}]
        self.assertFalse(m.has_changed())

    def test_append_dict(self):
        class TestSubmodel(BaseModel):
            text: str = Field(default="default")

        class TestModel(BaseModel):
            field: Optional[List[TestSubmodel]] = Field(default=[])

        m = TestModel()
        m.field.append({"text": "value"})
        # dict is converted to object next time the field is retrieved
        self.assertIsInstance(m.field[0], BaseModel)
        self.assertEqual(m.field[0].text, "value")

    def test_ordering(self):
        class TestSubmodel(BaseModel):
            txt: Optional[str] = Field()

        class TestModel(BaseModel):
            num: Optional[int] = Field()
            txt: Optional[str] = Field()
            sub: Optional[TestSubmodel] = Field()
            dct: Optional[Dict[str, TestSubmodel]] = Field()

        m1 = TestModel()
        m2 = TestModel()
        self.assertEqual(m1, m2)

        m1 = TestModel(num=1)
        m2 = TestModel(num=2)
        self.assertNotEqual(m1, m2)
        self.assertLess(m1, m2)
        self.assertGreater(m2, m1)

        m1 = TestModel(txt="a")
        m2 = TestModel(txt="b")
        self.assertNotEqual(m1, m2)
        self.assertLess(m1, m2)
        self.assertGreater(m2, m1)

        m1 = TestModel(sub={})
        m2 = TestModel(sub={})
        self.assertEqual(m1, m2)

        m1 = TestModel(sub={"txt": "a"})
        m2 = TestModel(sub={"txt": "b"})
        self.assertNotEqual(m1, m2)
        self.assertLess(m1, m2)
        self.assertGreater(m2, m1)

        m1 = TestModel(dct={})
        m2 = TestModel(dct={})
        self.assertEqual(m1, m2)

        m1 = TestModel(dct={"a": TestSubmodel()})
        m2 = TestModel(dct={"b": TestSubmodel()})
        self.assertNotEqual(m1, m2)
        self.assertLess(m1, m2)
        self.assertGreater(m2, m1)

        # dict ordering doesn't matter
        m1 = TestModel(dct={"a": TestSubmodel(), "b": TestSubmodel()})
        m2 = TestModel(dct={"b": TestSubmodel(), "a": TestSubmodel()})
        self.assertEqual(m1, m2)


if __name__ == "__main__":
    unittest.main()
