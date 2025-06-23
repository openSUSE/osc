import inspect
from typing import List
from typing import Optional

from .connection import GiteaHTTPResponse


class GiteaModel:
    def __init__(self, data, *, response: Optional[GiteaHTTPResponse] = None):
        self._data = data
        self._response = response

    def dict(self, exclude_columns: Optional[List[str]] = None):

        exclude_columns = exclude_columns or []
        result = {}

        for mro in inspect.getmro(self.__class__):
            for name, value in vars(mro).items():
                if name.endswith("_obj"):
                    continue

                found = 0
                for i in exclude_columns:
                    if i == name:
                        found = 1
                        break

                if found:
                    continue

                if isinstance(value, property):
                    obj = getattr(self, name)
                    try:
                        result[name] = obj
                    except Exception:
                        pass  # ignore objects that cannot fit to dictionary

        return result
