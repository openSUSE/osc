from . import tty
from . import widechar


class KeyValueTable:
    class NewLine:
        pass

    def __init__(self):
        self.rows = []

    def add(self, key, value, color=None, key_color=None, indent=0):
        if value is None:
            lines = []
        elif isinstance(value, (list, tuple)):
            lines = value[:]
        else:
            lines = value.splitlines()

        if not lines:
            lines = [""]

        # add the first line with the key
        self.rows.append((key, lines[0], color, key_color, indent))

        # then add the continuation lines without the key
        for line in lines[1:]:
            self.rows.append(("", line, color, key_color, 0))

    def newline(self):
        self.rows.append((self.NewLine, None, None, None, 0))

    def __str__(self):
        if not self.rows:
            return ""

        col1_width = max([widechar.wc_width(key) + indent for key, _, _, _, indent in self.rows if key != self.NewLine])
        result = []
        skip = False
        for row_num in range(len(self.rows)):
            if skip:
                skip = False
                continue

            key, value, color, key_color, indent = self.rows[row_num]

            if key == self.NewLine:
                result.append("")
                continue

            next_indent = 0  # fake value
            if not value and row_num < len(self.rows) - 1:
                # let's peek if there's a continuation line we could merge instead of the blank value
                next_key, next_value, next_color, next_key_color, next_indent = self.rows[row_num + 1]
                if not next_key:
                    value = next_value
                    color = next_color
                    key_color = next_key_color
                    row_num += 1
                    skip = True

            line = indent * " "

            if not value and next_indent > 0:
                # no value, the key represents a section followed by indented keys -> skip ljust() and " : " separator
                line += tty.colorize(key, key_color)
            else:
                line += tty.colorize(widechar.wc_ljust(key, col1_width - indent), key_color)
                if not key:
                    # continuation line without a key -> skip " : " separator
                    line += "   "
                else:
                    line += " : "
                line += tty.colorize(value, color)

            result.append(line)

        return "\n".join(result)
