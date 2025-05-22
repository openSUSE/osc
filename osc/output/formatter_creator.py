from . import formatter


class FormatterCreator:
    def __init__(self):
        self.rows = []

    def default_formatter(self):
        return formatter.FormatterText()

    def formatter_from_args(self, args):
        output_format = args.format
        if args.json:
            output_format = "json"

        return self.formatter_from_string(output_format)

    def formatter_from_string(self, output_format):
        if output_format and output_format == "json":
            return formatter.FormatterJson()
        else:
            return formatter.FormatterText()

