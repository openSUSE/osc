import sys
from json import dumps


class FormatterText:
    def __init__(self):
        self.rows = []

    def start(self):
        pass

    def finish(self, msg):
        print(msg, file=sys.stderr)

    def echo(self, obj):
        pass

    def format_list(self, lst):
        for o in lst:
            print(o.format_output(self))

    def new_table(self):
        from . import KeyValueTable

        return KeyValueTable()


class FormatterJson:
    def __init__(self):
        self.rows = []

    def start(self):
        pass

    def finish(self, msg):
        print(dumps(self.rows))

        print(msg, file=sys.stderr)

    def echo(self, obj):
        pass

    def format_list(self, lst):
        if not lst:
            return

        res = []
        for o in lst:
            res.append(o.format_output(self).dict())

        self.rows.append(res)

    def new_table(self):
        from . import KeyValueTableJson

        return KeyValueTableJson()
