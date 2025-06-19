import io
from typing import Any
from typing import IO
from typing import NoReturn


try:
    import yaml as pyyaml

    PYYAML = True
except ImportError:
    PYYAML = False


try:
    import ruamel.yaml

    RUAMEL_YAML = True
except ImportError:
    RUAMEL_YAML = False
    if not PYYAML:
        # fallback to PyYAML not possible, re-throw the exception
        raise


__all__ = (
    "yaml_load",
    "yaml_loads",
    "yaml_dump",
    "yaml_dumps",
)


def yaml_load(f: IO) -> Any:
    """
    Deserialize YAML from a file-like object ``f``.
    """
    if RUAMEL_YAML:
        return _ruamel_yaml_load(f)
    return _pyyaml_load(f)


def yaml_loads(s: str) -> Any:
    """
    Deserialize YAML from a string.
    """
    if RUAMEL_YAML:
        return _ruamel_yaml_loads(s)
    return _pyyaml_loads(s)


def yaml_dump(data: Any, f: IO) -> NoReturn:
    """
    Serialize ``data`` to YAML format and write it to file-like object ``f``.
    """
    if RUAMEL_YAML:
        _ruamel_yaml_dump(data, f)
    else:
        _pyyaml_dump(data, f)


def yaml_dumps(data: Any) -> str:
    """
    Serialize ``data`` to YAML format and return it as a string.
    """
    if RUAMEL_YAML:
        return _ruamel_yaml_dumps(data)
    return _pyyaml_dumps(data)


def _ruamel_yaml_load(f: IO) -> Any:
    yaml = ruamel.yaml.YAML(typ="safe")
    return yaml.load(f)


def _ruamel_yaml_loads(s: str) -> Any:
    return _ruamel_yaml_load(io.StringIO(s))


def _ruamel_yaml_dump(data: Any, f: IO) -> NoReturn:
    yaml = ruamel.yaml.YAML(typ="safe")
    yaml.default_flow_style = False
    yaml.dump(data, f)


def _ruamel_yaml_dumps(data: Any) -> str:
    with io.StringIO() as f:
        _ruamel_yaml_dump(data, f)
        f.seek(0)
        return f.read()


def _pyyaml_load(f: IO) -> Any:
    return pyyaml.safe_load(f)


def _pyyaml_loads(s: str) -> Any:
    return _pyyaml_load(io.StringIO(s))


def _pyyaml_dump(data: Any, f: IO) -> NoReturn:
    pyyaml.safe_dump(data, f, default_flow_style=False, sort_keys=True)


def _pyyaml_dumps(data: Any) -> str:
    with io.StringIO() as f:
        _pyyaml_dump(data, f)
        f.seek(0)
        return f.read()
