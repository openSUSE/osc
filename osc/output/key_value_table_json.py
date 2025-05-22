from json import dumps


class KeyValueTableJson:

    def __init__(self, min_key_length: int = 0):
        self.rows = {}

    def add(self, key, value, color=None, key_color=None, indent=0):
        self.rows[key.lower()] = value

    def newline(self):
        pass

    def __str__(self):
        return dumps(self.rows)

    def dict(self):
        return self.rows
