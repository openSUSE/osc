from typing import Optional


class Configuration:
    """
    A wrapper to configuration.yaml file that lives in obs/configuration, in the main branch.
    """

    @classmethod
    def from_file(cls, path: str) -> "Configuration":
        from ..util import yaml as osc_yaml

        with open(path, "r", encoding="utf-8") as f:
            data = osc_yaml.yaml_load(f)
        obj = cls(data)
        return obj

    @classmethod
    def from_string(cls, text: str) -> "Configuration":
        from ..util import yaml as osc_yaml

        data = osc_yaml.yaml_loads(text)
        obj = cls(data)
        return obj

    def __init__(self, data: dict):
        self._data = data

    @property
    def obs_apiurl(self) -> Optional[str]:
        return self._data.get("obs_apiurl", None)
