"""
This module implements a lightweight and limited alternative
to pydantic's BaseModel and Field classes.
It works on python 3.6+.

This module IS NOT a supported API, it is meant for osc internal use only.
"""

import inspect
import sys
import types
from typing import get_type_hints

# supported types
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


__all__ = (
    "BaseModel",
    "Field",
    "NotSet",
    "FromParent",
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
    def __init__(self, field_name):
        self.field_name = field_name

    def __repr__(self):
        return f"FromParent(field_name={self.field_name})"


class Field(property):
    def __init__(
        self,
        default: Any = NotSet,
        description: Optional[str] = None,
        exclude: bool = False,
        **extra,
    ):
        # the default value; it can be a factory function that is lazily evaluated on the first use
        # model sets it to None if it equals to NotSet (for better usability)
        self.default = default

        # whether the field was set
        self.is_set = False

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
            return types[0]
        return origin_type

    @property
    def is_optional(self):
        origin_type = get_origin(self.type) or self.type
        return origin_type == Union and len(self.type.__args__) == 2 and type(None) in self.type.__args__

    @property
    def is_model(self):
        return inspect.isclass(self.origin_type) and issubclass(self.origin_type, BaseModel)

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
            if origin_type == Union:
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
            return getattr(obj, f"_{self.name}")
        except AttributeError:
            pass

        if isinstance(self.default, FromParent):
            if obj._parent is None:
                raise RuntimeError(f"The field '{self.name}' has default {self.default} but the model has no parent set")
            return getattr(obj._parent, self.default.field_name or self.name)

        if self.default is NotSet:
            raise RuntimeError(f"The field '{self.name}' has no default")

        # lazy evaluation of a factory function on first use
        if callable(self.default):
            self.default = self.default()

        # if this is a model field, convert dict to a model instance
        if self.is_model and isinstance(self.default, dict):
            new_value = self.origin_type()  # pylint: disable=not-callable
            for k, v in self.default.items():
                setattr(new_value, k, v)
            self.default = new_value

        return self.default

    def set(self, obj, value):
        # if this is a model field, convert dict to a model instance
        if self.is_model and isinstance(value, dict):
            new_value = self.origin_type()  # pylint: disable=not-callable
            for k, v in value.items():
                setattr(new_value, k, v)
            value = new_value

        self.validate_type(value)
        setattr(obj, f"_{self.name}", value)
        self.is_set = True


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


class BaseModel(metaclass=ModelMeta):
    __fields__: Dict[str, Field]

    def __init__(self, **kwargs):
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
            raise TypeError(f"The following kwargs do not match any field: {unknown_fields_str}")

        if uninitialized_fields:
            uninitialized_fields_str = ", ".join([f"'{i}'" for i in uninitialized_fields])
            raise TypeError(
                f"The following fields are not initialized and have no default either: {uninitialized_fields_str}"
            )

        for name, field in self.__fields__.items():
            field.validate_type(getattr(self, name))

    def dict(self, exclude_unset=False):
        result = {}
        for name, field in self.__fields__.items():
            if field.exclude:
                continue
            if exclude_unset and not field.is_set and field.is_optional:
                # include only mandatory fields and optional fields that were set to an actual value
                continue
            if field.is_model:
                result[name] = getattr(self, name).dict(exclude_unset=exclude_unset)
            else:
                result[name] = getattr(self, name)
        return result
