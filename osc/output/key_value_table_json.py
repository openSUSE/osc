from json import dumps

from . import tty
from . import widechar


class KeyValueTableJson:

    def __init__(self, min_key_length: int = 0):
        self.rows = {}
        self.min_key_length = min_key_length # ignored

    def add(self, key, value, color=None, key_color=None, indent=0):
        self.rows[key.lower()] = value

    def newline(self):
        pass

    def __str__(self):
        return dumps(self.rows)
