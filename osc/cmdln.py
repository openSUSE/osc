"""
A modern, lightweight alternative to cmdln.py from https://github.com/trentm/cmdln
"""


import argparse
import inspect
import sys
import textwrap


def option(*args, **kwargs):
    """
    Decorator to add an option to the optparser argument of a Cmdln subcommand.

    Example:
        class MyShell(cmdln.Cmdln):
            @cmdln.option("-f", "--force", help="force removal")
            def do_remove(self, subcmd, opts, *args):
                #...
    """
    def decorate(f):
        if not hasattr(f, "options"):
            f.options = []
        new_args = [i for i in args if i]
        f.options.insert(0, (new_args, kwargs))
        return f
    return decorate


def alias(*aliases):
    """
    Decorator to add aliases for Cmdln.do_* command handlers.

    Example:
        class MyShell(cmdln.Cmdln):
            @cmdln.alias("!", "sh")
            def do_shell(self, argv):
                #...implement 'shell' command
    """
    def decorate(f):
        if not hasattr(f, "aliases"):
            f.aliases = []
        f.aliases += aliases
        return f
    return decorate


def name(name):
    """
    Decorator to explicitly name a Cmdln subcommand.

    Example:
        class MyShell(cmdln.Cmdln):
            @cmdln.name("cmd-with-dashes")
            def do_cmd_with_dashes(self, subcmd, opts):
                #...
    """
    def decorate(f):
        f.name = name
        return f
    return decorate


def hide(value=True):
    """
    For obsolete calls, hide them in help listings.

    Example:
        class MyShell(cmdln.Cmdln):
            @cmdln.hide()
            def do_shell(self, argv):
                #...implement 'shell' command
    """
    def decorate(f):
        f.hidden = bool(value)
        return f
    return decorate


class HelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _split_lines(self, text, width):
        # remove the leading and trailing whitespaces to avoid printing unwanted blank lines
        text = text.strip()

        result = []
        for line in text.splitlines():
            if not line.strip():
                # textwrap normally returns [] on a string that contains only whitespaces; we want [""] to print a blank line
                result.append("")
            else:
                result.extend(textwrap.wrap(line, width))
        return result

    def _format_action(self, action):
        if isinstance(action, argparse._SubParsersAction):
            parts = []
            subactions = action._get_subactions()
            subactions.sort(key=lambda x: x.metavar)
            for i in subactions:
                if i.help == argparse.SUPPRESS:
                    # don't display commands with suppressed help
                    continue
                if len(i.metavar) > 20:
                    parts.append("%*s%-21s" % (self._current_indent, "", i.metavar))
                    parts.append("%*s %s" % (self._current_indent + 21, "", i.help))
                else:
                    parts.append("%*s%-21s %s" % (self._current_indent, "", i.metavar, i.help))
            return "\n".join(parts)
        return super()._format_action(action)


class Cmdln:
    def get_argparser_usage(self):
        return "%(prog)s [global opts] <command> [--help] [opts] [args]"

    def get_subcommand_prog(self, subcommand):
        return f"{self.argparser.prog} [global opts] {subcommand}"

    def _remove_leading_spaces_from_text(self, text):
        lines = text.splitlines()
        lines = self._remove_leading_spaces_from_lines(lines)
        return "\n".join(lines)

    def _remove_leading_spaces_from_lines(self, lines):
        # compute the indentation (leading spaces) in the docstring
        leading_spaces = 0
        for line in lines:
            line_leading_spaces = len(line) - len(line.lstrip(' '))
            if leading_spaces == 0:
                leading_spaces = line_leading_spaces
            leading_spaces = min(leading_spaces, line_leading_spaces)
        # dedent the lines (remove leading spaces)
        lines = [line[leading_spaces:] for line in lines]
        return lines

    def create_argparser(self):
        """
        Create `.argparser` and `.subparsers`.
        Override this method to replace them with your own.
        """
        self.argparser = argparse.ArgumentParser(
            usage=self.get_argparser_usage(),
            description=self._remove_leading_spaces_from_text(self.__doc__),
            formatter_class=HelpFormatter,
        )
        self.subparsers = self.argparser.add_subparsers(
            title="commands",
            dest="command",
        )

        self.pre_argparse()
        self.add_global_options(self.argparser)

        # map command name to `do_*` function that runs the command
        self.cmd_map = {}

        # map aliases back to the command names
        self.alias_to_cmd_name_map = {}

        for attr in dir(self):
            if not attr.startswith("do_"):
                continue

            cmd_name = attr[3:]
            cmd_func = getattr(self, attr)

            # extract data from the function
            cmd_name = getattr(cmd_func, "name", cmd_name)
            options = getattr(cmd_func, "options", [])
            aliases = getattr(cmd_func, "aliases", [])
            hidden = getattr(cmd_func, "hidden", False)

            # map command name and aliases to the function
            self.cmd_map[cmd_name] = cmd_func
            self.alias_to_cmd_name_map[cmd_name] = cmd_name
            for i in aliases:
                self.cmd_map[i] = cmd_func
                self.alias_to_cmd_name_map[i] = cmd_name

            if cmd_func.__doc__:
                # split doctext into lines, allow the first line to start at a new line
                help_lines = cmd_func.__doc__.lstrip().splitlines()

                # use the first line as help text
                help_text = help_lines.pop(0)

                # use the remaining lines as description
                help_lines = self._remove_leading_spaces_from_lines(help_lines)
                help_desc = "\n".join(help_lines)
                help_desc = help_desc.strip()
            else:
                help_text = ""
                help_desc = ""

            if hidden:
                help_text = argparse.SUPPRESS

            subparser = self.subparsers.add_parser(
                cmd_name,
                aliases=aliases,
                help=help_text,
                description=help_desc,
                prog=self.get_subcommand_prog(cmd_name),
                formatter_class=HelpFormatter,
                conflict_handler="resolve",
            )

            # add hidden copy of global options so they can be used in any place
            self.add_global_options(subparser, suppress=True)

            # add sub-command options, overriding hidden copies of global options if needed (due to conflict_handler="resolve")
            for option_args, option_kwargs in options:
                subparser.add_argument(*option_args, **option_kwargs)

    def argparse_error(self, *args, **kwargs):
        """
        Raise an argument parser error.
        Automatically pick the right parser for the main program or a subcommand.
        """
        if not self.options.command:
            parser = self.argparser
        else:
            parser = self.subparsers._name_parser_map.get(self.options.command, self.argparser)
        parser.error(*args, **kwargs)

    def pre_argparse(self):
        """
        Hook method executed after `.main()` creates `.argparser` instance
        and before `parse_args()` is called.
        """
        pass

    def add_global_options(self, parser, suppress=False):
        """
        Add options to the main argument parser and all subparsers.
        """
        pass

    def post_argparse(self):
        """
        Hook method executed after `.main()` calls `parse_args()`.
        When called, `.options` and `.args` hold the results of `parse_args()`.
        """
        pass

    def main(self, argv=None):
        if argv is None:
            argv = sys.argv
        else:
            argv = argv[:]  # don't modify caller's list

        self.create_argparser()

        self.options, self.args = self.argparser.parse_known_args(argv[1:])
        unrecognized = [i for i in self.args if i.startswith("-")]
        if unrecognized:
            self.argparser.error(f"unrecognized arguments: {' '.join(unrecognized)}")

        self.post_argparse()

        if not self.options.command:
            self.argparser.error("Please specify a command")

        # find the `do_*` function to call by its name
        cmd = self.cmd_map[self.options.command]
        # run the command with parsed args

        sig = inspect.signature(cmd)
        arg_names = list(sig.parameters.keys())
        if arg_names == ["subcmd", "opts"]:
            # positional args specified manually via @cmdln.option
            if self.args:
                self.argparser.error(f"unrecognized arguments: {' '.join(self.args)}")
            cmd(self.options.command, self.options)
        elif arg_names == ["subcmd", "opts", "args"]:
            # positional args are the remaining (unrecognized) args
            cmd(self.options.command, self.options, *self.args)
        else:
            # positional args are the remaining (unrecongnized) args
            # and the do_* handler takes other arguments than "subcmd", "opts", "args"
            import warnings
            warnings.warn(
                f"do_{self.options.command}() handler has deprecated signature. "
                f"It takes the following args: {arg_names}, while it should be taking ['subcmd', 'opts'] "
                f"and handling positional arguments explicitly via @cmdln.option.",
                FutureWarning
            )
            try:
                cmd(self.options.command, self.options, *self.args)
            except TypeError as e:
                if e.args[0].startswith("do_"):
                    sys.exit(str(e))
                raise

    @alias("?")
    def do_help(self, subcmd, opts, *args):
        """
        Give detailed help on a specific sub-command

        usage:
          %(prog)s [SUBCOMMAND]
        """
        if not args:
            self.argparser.print_help()
            return

        for action in self.argparser._actions:
            if not isinstance(action, argparse._SubParsersAction):
                continue

            for choice, subparser in action.choices.items():
                if choice == args[0]:
                    subparser.print_help()
                    return
