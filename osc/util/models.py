"""
This module implements a lightweight and limited alternative
to pydantic's BaseModel and Field classes.
It works on python 3.6+.

This module IS NOT a supported API, it is meant for osc internal use only.
"""

import copy
import functools
import inspect
import sys
import tempfile
import types
import typing
from typing import Callable
from typing import get_type_hints
from xml.etree import ElementTree as ET

# supported types
from enum import Enum
from typing import Any
from typing import Dict
from typing import List
from typing import NewType
from typing import Optional
from typing import Tuple
from typing import Union

if sys.version_info < (3, 8):

    def get_origin(typ):
        result = getattr(typ, "__origin__", None)
        bases = getattr(result, "__orig_bases__", None)
        if bases:
            result = bases[0]
        return result

else:
    from typing import get_origin


# types.UnionType was added in Python 3.10
if sys.version_info < (3, 10):
    class UnionType:
        pass
else:
    from types import UnionType


import urllib3.response

from . import xml


__all__ = (
    "BaseModel",
    "XmlModel",
    "Field",
    "NotSet",
    "FromParent",
    "Enum",
    "Dict",
    "List",
    "NewType",
    "Optional",
    "Tuple",
    "Union",
)


class NotSetClass:
    def __repr__(self):
        return "NotSet"

    def __bool__(self):
        return False


NotSet = NotSetClass()


class FromParent(NotSetClass):
    def __init__(self, field_name, *, fallback=NotSet):
        self.field_name = field_name
        self.fallback = fallback

    def __repr__(self):
        return f"FromParent(field_name={self.field_name})"

# HACK: inheriting from Any fixes the following mypy error:
#       Incompatible types in assignment (expression has type "Field", variable has type "X | None")  [assignment]
class Field(property, *([Any] if typing.TYPE_CHECKING else [])):
    def __init__(
        self,
        default: Any = NotSet,
        description: Optional[str] = None,
        exclude: bool = False,
        get_callback: Optional[Callable] = None,
        **extra,
    ):
        # the default value; it can be a factory function that is lazily evaluated on the first use
        # model sets it to None if it equals to NotSet (for better usability)
        self.default = default

        # a flag indicating, whether the default is a callable with lazy evalution
        self.default_is_lazy = callable(self.default)

        # the name of model's attribute associated with this field instance - set from the model
        self.name = None

        # the type of this field instance - set from the model
        self.type = None

        # the description of the field
        self.description = description

        # docstring - for sphinx and help()
        self.__doc__ = self.description
        if self.__doc__:
            # append information about the default value
            if isinstance(self.default, FromParent):
                self.__doc__ += f"\n\nDefault: inherited from parent config's field ``{self.default.field_name}``"
            elif self.default is not NotSet:
                self.__doc__ += f"\n\nDefault: ``{self.default}``"

        # whether to exclude this field from export
        self.exclude = exclude

        # optional callback to postprocess returned field value
        # it takes (model_instance, value) and returns modified value
        self.get_callback = get_callback

        # extra fields
        self.extra = extra

        # create an instance specific of self.get() so we can annotate it in the model
        self.get_copy = types.FunctionType(
            self.get.__code__,
            self.get.__globals__,
            self.get.__name__,
            self.get.__defaults__,
            self.get.__closure__,
        )
        # turn function into a method by binding it to the instance
        self.get_copy = types.MethodType(self.get_copy, self)

        super().__init__(fget=self.get_copy, fset=self.set, doc=description)

    @property
    def origin_type(self):
        origin_type = get_origin(self.type) or self.type
        if self.is_optional:
            types = [i for i in self.type.__args__ if i != type(None)]
            return get_origin(types[0]) or types[0]
        return origin_type

    @property
    def inner_type(self):
        if self.is_optional:
            types = [i for i in self.type.__args__ if i != type(None)]
            type_ = types[0]
        else:
            type_ = self.type

        if get_origin(type_) != list:
            return None

        if not hasattr(type_, "__args__"):
            return None

        inner_type = [i for i in type_.__args__ if i != type(None)][0]
        return inner_type

    @property
    def is_optional(self):
        origin_type = get_origin(self.type) or self.type
        return origin_type in (Union, UnionType) and type(None) in self.type.__args__

    @property
    def is_model(self):
        return inspect.isclass(self.origin_type) and issubclass(self.origin_type, BaseModel)

    @property
    def is_model_list(self):
        return inspect.isclass(self.inner_type) and issubclass(self.inner_type, BaseModel)

    def validate_type(self, value, expected_types=None):
        if not expected_types and self.is_optional and value is None:
            return True

        if expected_types is None:
            expected_types = (self.type,)
        elif not isinstance(expected_types, (list, tuple)):
            expected_types = (expected_types,)

        valid_type = False

        for expected_type in expected_types:
            if valid_type:
                break

            origin_type = get_origin(expected_type) or expected_type

            # unwrap Union
            if origin_type in (Union, UnionType):
                if value is None and type(None) in expected_type.__args__:
                    valid_type = True
                    continue

                valid_type |= self.validate_type(value, expected_types=expected_type.__args__)
                continue

            # unwrap NewType
            if (callable(NewType) or isinstance(origin_type, NewType)) and hasattr(origin_type, "__supertype__"):
                valid_type |= self.validate_type(value, expected_types=(origin_type.__supertype__,))
                continue

            if (
                inspect.isclass(expected_type)
                and issubclass(expected_type, BaseModel)
                and isinstance(value, (expected_type, dict))
            ):
                valid_type = True
                continue

            if (
                inspect.isclass(expected_type)
                and issubclass(expected_type, Enum)
            ):
                # test if the value is part of the enum
                expected_type(value)
                valid_type = True
                continue

            if not isinstance(value, origin_type):
                msg = f"Field '{self.name}' has type '{self.type}'. Cannot assign a value with type '{type(value).__name__}'."
                raise TypeError(msg)

            # the type annotation has no arguments -> no need to check those
            if not getattr(expected_type, "__args__", None):
                valid_type = True
                continue

            if origin_type in (list, tuple):
                valid_type_items = True
                for i in value:
                    valid_type_items &= self.validate_type(i, expected_type.__args__)
                valid_type |= valid_type_items
            elif origin_type in (dict,):
                valid_type_items = True
                for k, v in value.items():
                    valid_type_items &= self.validate_type(k, expected_type.__args__[0])
                    valid_type_items &= self.validate_type(v, expected_type.__args__[1])
                valid_type |= valid_type_items
            else:
                raise TypeError(f"Field '{self.name}' has unsupported type '{self.type}'.")

        return valid_type

    def get(self, obj):
        try:
            result = obj._values[self.name]

            # convert dictionaries into objects
            # we can't do it earlier because list is a standalone object that is not under our control
            if result is not None and self.is_model_list:
                for num, i in enumerate(result):
                    if isinstance(i, dict):
                        klass = self.inner_type
                        result[num] = klass(**i, _parent=obj)

            if self.get_callback is not None:
                result = self.get_callback(obj, result)

            return result
        except KeyError:
            pass

        try:
            result = obj._defaults[self.name]
            if isinstance(result, (dict, list)):
                # make a deepcopy to avoid problems with mutable defaults
                result = copy.deepcopy(result)
                obj._values[self.name] = result
            if self.get_callback is not None:
                result = self.get_callback(obj, result)
            return result
        except KeyError:
            pass

        if isinstance(self.default, FromParent):
            if obj._parent is None:
                if self.default.fallback is not NotSet:
                    return self.default.fallback
                else:
                    raise RuntimeError(f"The field '{self.name}' has default {self.default} but the model has no parent set")
            return getattr(obj._parent, self.default.field_name or self.name)

        if self.default is NotSet:
            raise RuntimeError(f"The field '{self.name}' has no default")

        # make a deepcopy to avoid problems with mutable defaults
        default = copy.deepcopy(self.default)

        # lazy evaluation of a factory function on first use
        if callable(default):
            default = default()

        # if this is a model field, convert dict to a model instance
        if self.is_model and isinstance(default, dict):
            cls = self.origin_type
            new_value = cls()  # pylint: disable=not-callable
            for k, v in default.items():
                setattr(new_value, k, v)
            default = new_value

        obj._defaults[self.name] = default
        return default

    def set(self, obj, value):
        # if this is a model field, convert dict to a model instance
        if self.is_model and isinstance(value, dict):
            # initialize a model instance from a dictionary
            klass = self.origin_type
            value = klass(**value, _parent=obj)  # pylint: disable=not-callable
        elif self.is_model_list and isinstance(value, list):
            new_value = []
            for i in value:
                if isinstance(i, dict):
                    klass = self.inner_type
                    new_value.append(klass(**i, _parent=obj))
                else:
                    i._parent = obj
                    new_value.append(i)
            value = new_value
        elif self.is_model and isinstance(value, str) and hasattr(self.origin_type, "XML_TAG_FIELD"):
            klass = self.origin_type
            key = getattr(self.origin_type, "XML_TAG_FIELD")
            value = klass(**{key: value}, _parent=obj)
        elif self.is_model and value is not None:
            value._parent = obj

        self.validate_type(value)
        obj._values[self.name] = value


class ModelMeta(type):
    def __new__(mcs, name, bases, attrs):
        new_cls = super().__new__(mcs, name, bases, attrs)
        new_cls.__fields__ = {}

        # NOTE: dir() doesn't preserve attribute order
        # we need to iterate through __mro__ classes to workaround that
        for parent_cls in reversed(new_cls.__mro__):
            for field_name in parent_cls.__dict__:
                if field_name in new_cls.__fields__:
                    continue
                field = getattr(new_cls, field_name)
                if not isinstance(field, Field):
                    continue
                new_cls.__fields__[field_name] = field

        # fill model specific details back to the fields
        for field_name, field in new_cls.__fields__.items():
            # property name associated with the field in this model
            field.name = field_name

            # field type associated with the field in this model
            field.type = get_type_hints(new_cls)[field_name]

            # set annotation for the getter so it shows up in sphinx
            field.get_copy.__func__.__annotations__ = {"return": field.type}

            # set 'None' as the default for optional fields
            if field.default is NotSet and field.is_optional:
                field.default = None

        return new_cls


@functools.total_ordering
class BaseModel(metaclass=ModelMeta):
    __fields__: Dict[str, Field]

    def __setattr__(self, name, value):
        if getattr(self, "_allow_new_attributes", True) or hasattr(self.__class__, name) or hasattr(self, name):
            # allow setting properties - test if they exist in the class
            # also allow setting existing attributes that were previously initialized via __dict__
            return super().__setattr__(name, value)
        raise AttributeError(f"Setting attribute '{self.__class__.__name__}.{name}' is not allowed")

    def __init__(self, **kwargs):
        self._allow_new_attributes = True
        self._defaults = {}  # field defaults cached in field.get()
        self._values = {}  # field values explicitly set after initializing the model
        self._parent = kwargs.pop("_parent", None)

        uninitialized_fields = []

        for name, field in self.__fields__.items():
            if name not in kwargs:
                if field.default is NotSet:
                    uninitialized_fields.append(field.name)
                continue
            value = kwargs.pop(name)
            setattr(self, name, value)

        if kwargs:
            unknown_fields_str = ", ".join([f"'{i}'" for i in kwargs])
            raise TypeError(f"The following kwargs of '{self.__class__.__name__}.__init__()' do not match any field: {unknown_fields_str}")

        if uninitialized_fields:
            uninitialized_fields_str = ", ".join([f"'{i}'" for i in uninitialized_fields])
            raise TypeError(
                f"The following fields of '{self.__class__.__name__}' object are not initialized and have no default either: {uninitialized_fields_str}"
            )

        for name, field in self.__fields__.items():
            field.validate_type(getattr(self, name))

        self._snapshot = {}  # copy of ``self.dict()`` so we can determine if the object has changed later on
        self.do_snapshot()

        self._allow_new_attributes = False

    def _get_cmp_data(self):
        result = []
        for name, field in self.__fields__.items():
            if field.exclude:
                continue
            value = getattr(self, name)
            if isinstance(value, dict):
                value = sorted(list(value.items()))
            result.append((name, value))
        return result

    def __eq__(self, other):
        if type(self) != type(other):
            return False
        return self._get_cmp_data() == other._get_cmp_data()

    def __lt__(self, other):
        if type(self) != type(other):
            return False
        return self._get_cmp_data() < other._get_cmp_data()

    def dict(self):
        result = {}
        for name, field in self.__fields__.items():
            if field.exclude:
                continue
            value = getattr(self, name)
            if value is not None and field.is_model:
                result[name] = value.dict()
            elif value is not None and field.is_model_list:
                result[name] = [i.dict() for i in value]
            else:
                result[name] = value

        return result

    def do_snapshot(self):
        """
        Save ``self.dict()`` result as a new starting point for detecting changes in the object data.
        """
        self._snapshot = self.dict()

    def has_changed(self):
        """
        Determine if the object data has changed since its creation or the last snapshot.
        """
        return self.dict() != self._snapshot


class XmlModel(BaseModel):
    XML_TAG: Optional[str] = None

    _apiurl: Optional[str] = Field(
        exclude=True,
        default=FromParent("_apiurl", fallback=None),
    )

    def to_xml(self, *, with_comments: bool = False) -> ET.Element:
        xml_tag = None

        # check if there's a special field that sets the tag
        for field_name, field in self.__fields__.items():
            xml_set_tag = field.extra.get("xml_set_tag", False)
            if xml_set_tag:
                value = getattr(self, field_name)
                xml_tag = value
                break

        # use the value from the class
        if xml_tag is None:
            xml_tag = self.XML_TAG

        assert xml_tag is not None
        root = ET.Element(xml_tag)

        if with_comments:
            comment = [
                "",
                "The commented attributes and elements only provide hints on the XML structure.",
                "See OBS documentation such as XML schema files for more details:",
                "https://github.com/openSUSE/open-build-service/tree/master/docs/api/api",
                "",
            ]
            comment_node = ET.Comment(text="\n".join(comment))
            root.append(comment_node)

        for field_name, field in self.__fields__.items():
            if field.exclude:
                continue
            xml_attribute = field.extra.get("xml_attribute", False)
            xml_set_tag = field.extra.get("xml_set_tag", False)
            xml_set_text = field.extra.get("xml_set_text", False)
            xml_name = field.extra.get("xml_name", field_name)
            xml_wrapped = field.extra.get("xml_wrapped", False)
            xml_item_name = field.extra.get("xml_item_name", xml_name)

            if xml_set_tag:
                # a special case when the field determines the top-level tag name
                continue

            if with_comments:
                if xml_attribute:
                    comment = f'{xml_name}=""'
                else:
                    comment = f"<{xml_name}></{xml_name}>"

                comment_node = ET.Comment(text=f" {comment} ")
                root.append(comment_node)

            value = getattr(self, field_name)
            if value is None:
                # skip fields that are not set
                continue

            # if value is wrapped into an external element, create it
            if xml_wrapped:
                wrapper_node = ET.SubElement(root, xml_name)
            else:
                wrapper_node = root

            if xml_set_text:
                wrapper_node.text = str(value)
                continue

            if field.origin_type == list:
                for entry in value:
                    if isinstance(entry, dict):
                        klass = field.inner_type
                        obj = klass(**entry)
                        node = obj.to_xml()
                        wrapper_node.append(node)
                    elif field.inner_type and issubclass(field.inner_type, XmlModel):
                        wrapper_node.append(entry.to_xml())
                    else:
                        node = ET.SubElement(wrapper_node, xml_item_name)
                        if xml_attribute:
                            node.attrib[xml_attribute] = entry
                        else:
                            node.text = entry
            elif issubclass(field.origin_type, XmlModel):
                wrapper_node.append(value.to_xml())
            elif xml_attribute:
                wrapper_node.attrib[xml_name] = str(value)
            else:
                node = ET.SubElement(wrapper_node, xml_name)
                node.text = str(value)
        return root

    @classmethod
    def from_string(cls, string: str, *, apiurl: Optional[str] = None) -> "XmlModel":
        """
        Instantiate model from string.
        """
        root = xml.xml_fromstring(string)
        return cls.from_xml(root, apiurl=apiurl)

    @classmethod
    def from_file(cls, file: Union[str, typing.IO], *, apiurl: Optional[str] = None) -> "XmlModel":
        """
        Instantiate model from file.
        """
        root = xml.xml_parse(file).getroot()
        return cls.from_xml(root, apiurl=apiurl)

    def to_bytes(self, *, with_comments: bool = False) -> bytes:
        """
        Serialize the object as XML and return it as utf-8 encoded bytes.
        """
        root = self.to_xml(with_comments=with_comments)
        xml.xml_indent(root)
        return ET.tostring(root, encoding="utf-8")

    def to_string(self, *, with_comments: bool = False) -> str:
        """
        Serialize the object as XML and return it as a string.
        """
        return self.to_bytes(with_comments=with_comments).decode("utf-8")

    def to_file(self, file: Union[str, typing.IO], *, with_comments: bool = False) -> None:
        """
        Serialize the object as XML and save it to an utf-8 encoded file.
        """
        root = self.to_xml(with_comments=with_comments)
        xml.xml_indent(root)
        return ET.ElementTree(root).write(file, encoding="utf-8")

    @staticmethod
    def value_from_string(field, value):
        """
        Convert field value from string to the actual type of the field.
        """
        if field.origin_type is bool:
            if value.lower() in ["1", "yes", "true", "on"]:
                value = True
                return value
            if value.lower() in ["0", "no", "false", "off"]:
                value = False
                return value

        if field.origin_type is int:
            if not value or not value.strip():
                return None
            value = int(value)
            return value

        return value

    @classmethod
    def _remove_processed_node(cls, parent, node):
        """
        Remove a node that has been fully processed and is now empty.
        """
        if len(node) != 0:
            raise RuntimeError(f"Node {node} contains unprocessed child elements {list(node)}")
        if node.attrib:
            raise RuntimeError(f"Node {node} contains unprocessed attributes {node.attrib}")
        if node.text is not None and node.text.strip():
            raise RuntimeError(f"Node {node} contains unprocessed text {node.text}")
        if parent is not None:
            parent.remove(node)

    @classmethod
    def from_xml(cls, root: ET.Element, *, apiurl: Optional[str] = None):
        """
        Instantiate model from a XML root.
        """

        # We need to make sure we parse all data
        # and that's why we remove processed elements and attributes and check that nothing remains.
        # Otherwise we'd be sending partial XML back and that would lead to data loss.
        #
        # Let's make a copy of the xml tree because we'll destroy it during the process.
        orig_root = root
        root = copy.deepcopy(root)

        kwargs = {}
        for field_name, field in cls.__fields__.items():
            xml_attribute = field.extra.get("xml_attribute", False)
            xml_set_tag = field.extra.get("xml_set_tag", False)
            xml_set_text = field.extra.get("xml_set_text", False)
            xml_name = field.extra.get("xml_name", field_name)
            xml_wrapped = field.extra.get("xml_wrapped", False)
            xml_item_name = field.extra.get("xml_item_name", xml_name)
            value: Any
            node: Optional[ET.Element]

            if xml_set_tag:
                # field contains name of the ``root`` tag
                if xml_wrapped:
                    # the last node wins (overrides the previous nodes)
                    for node in root[:]:
                        value = node.tag
                        cls._remove_processed_node(root, node)
                else:
                    value = root.tag

                kwargs[field_name] = value
                continue

            if xml_set_text:
                # field contains the value (text) of the element
                if xml_wrapped:
                    # the last node wins (overrides the previous nodes)
                    for node in root[:]:
                        value = node.text
                        node.text = None
                        cls._remove_processed_node(root, node)
                else:
                    value = root.text
                    root.text = None

                value = value.strip()
                kwargs[field_name] = value
                continue

            if xml_attribute:
                # field is an attribute that contains a scalar
                if xml_name not in root.attrib:
                    continue
                value = cls.value_from_string(field, root.attrib.pop(xml_name))
                kwargs[field_name] = value
                continue

            if field.origin_type is list:
                if xml_wrapped:
                    wrapper_node = root.find(xml_name)
                    # we'll consider all nodes inside the wrapper node
                    nodes = wrapper_node[:] if wrapper_node is not None else None
                else:
                    wrapper_node = None
                    # we'll consider only nodes with matching name
                    nodes = root.findall(xml_item_name)

                if not nodes:
                    if wrapper_node is not None:
                        cls._remove_processed_node(root, wrapper_node)
                    continue

                values = []
                for node in nodes:
                    if field.is_model_list:
                        klass = field.inner_type
                        entry = klass.from_xml(node, apiurl=apiurl)

                        # clear node as it was checked in from_xml() already
                        node.text = None
                        node.attrib = {}
                        node[:] = []
                    else:
                        entry = cls.value_from_string(field, node.text)
                        node.text = None

                    values.append(entry)

                    if xml_wrapped:
                        cls._remove_processed_node(wrapper_node, node)
                    else:
                        cls._remove_processed_node(root, node)

                if xml_wrapped:
                    cls._remove_processed_node(root, wrapper_node)

                kwargs[field_name] = values
                continue

            if field.is_model:
                # field contains an instance of XmlModel
                assert xml_name is not None
                node = root.find(xml_name)
                if node is None:
                    continue
                klass = field.origin_type
                kwargs[field_name] = klass.from_xml(node, apiurl=apiurl)

                # clear node as it was checked in from_xml() already
                node.text = None
                node.attrib = {}
                node[:] = []

                cls._remove_processed_node(root, node)
                continue

            # field contains a scalar
            node = root.find(xml_name)
            if node is None:
                continue
            value = cls.value_from_string(field, node.text)
            node.text = None
            cls._remove_processed_node(root, node)
            if value is None:
                if field.is_optional:
                    continue
                value = ""
            kwargs[field_name] = value

        cls._remove_processed_node(None, root)

        obj = cls(**kwargs, _apiurl=apiurl)
        obj.__dict__["_root"] = orig_root
        return obj

    @classmethod
    def xml_request(
        cls,
        method: str,
        apiurl: str,
        path: List[str],
        query: Optional[dict] = None,
        headers: Optional[str] = None,
        data: Optional[str] = None,
    ) -> urllib3.response.HTTPResponse:
        from ..connection import http_request
        from ..core import makeurl
        url = makeurl(apiurl, path, query)
        # TODO: catch HTTPError and return the wrapped response as XmlModel instance
        return http_request(method, url, headers=headers, data=data)

    def do_update(self, other: "XmlModel") -> None:
        """
        Update values of the fields in the current model instance from another.
        """
        self._values = copy.deepcopy(other._values)

    def do_edit(self) -> Tuple[str, str, "XmlModel"]:
        """
        Serialize model as XML and open it in an editor for editing.
        Return a tuple with:
          * a string with original data
          * a string with edited data
          * an instance of the class with edited data loaded

        IMPORTANT: This method is always interactive.
        """
        from ..core import run_editor
        from ..output import get_user_input

        def write_file(f, data):
            f.seek(0)
            f.write(data)
            f.truncate()
            f.flush()

        with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", prefix="obs_xml_", suffix=".xml") as f:
            original_data = self.to_string()
            original_data_with_comments = self.to_string(with_comments=True)
            write_file(f, original_data_with_comments)

            while True:
                run_editor(f.name)
                try:
                    edited_obj = self.__class__.from_file(f.name, apiurl=self._apiurl)
                    f.seek(0)
                    edited_data = f.read()
                    break
                except Exception as e:
                    reply = get_user_input(
                        f"""
                        The edited data is not valid.
                        {e}
                        """,
                        answers={"a": "abort", "e": "edit", "u": "undo changes and edit"},
                    )
                    if reply == "a":
                        from .. import oscerr
                        raise oscerr.UserAbort()
                    elif reply == "e":
                        continue
                    elif reply == "u":
                        write_file(f, original_data_with_comments)
                        continue

        # strip comments, we don't need to increase traffic to the server
        edited_data = edited_obj.to_string()

        return original_data, edited_data, edited_obj
