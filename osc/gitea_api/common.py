import inspect
import os
import subprocess
from typing import List
from typing import Optional

from .connection import Connection
from .connection import GiteaHTTPResponse


class GiteaModel:
    def __init__(self, data, *, response: Optional[GiteaHTTPResponse] = None, conn: Optional[Connection] = None):
        self._data = data
        self._response = response
        self._conn = conn

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


def get_editor() -> List[str]:
    import shutil
    import shlex

    editor = os.getenv("EDITOR", None)
    if editor:
        candidates = [editor]
    else:
        candidates = ["vim", "vi"]

    editor_path = None
    args = None
    for i in candidates:
        i, *args = shlex.split(i)
        if i.startswith("/"):
            editor_path = i
        else:
            editor_path = shutil.which(i)

        if editor_path:
            break

    if not editor_path:
        raise RuntimeError(f"Unable to start editor '{candidates[0]}'")

    res = [editor_path]
    if args:
        res += args

    return res


def get_editor_command(file_path: str) -> List[str]:
    res = get_editor()
    res.append(file_path)
    return res


def run_editor(file_path: str):
    subprocess.run(get_editor_command(file_path), check=True)


def edit_message(template: Optional[str] = None) -> str:
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", prefix="git_obs_message_") as f:
        if template:
            f.write(template)
            f.flush()

        run_editor(f.name)

        f.seek(0)
        return f.read()


def dt_sanitize(date_time: str, tz_name: Optional[str] = "UTC"):
    """
    Sanitize ``date_time`` string to "YYYY-MM-DD HH:MM" format.
    Also convert it to the given time zone.
    If ``tz_name`` is None, the time zone is the local time.
    """
    import dateutil

    dt = dateutil.parser.parse(timestr=date_time)
    tz = dateutil.tz.gettz(tz_name)
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M")
