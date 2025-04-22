import argparse
import copy
import importlib
import inspect
import os
import pkgutil
import sys
import textwrap
from typing import List
from typing import Tuple

from . import cmdln


# python3.6 requires reading sys.real_prefix to detect virtualenv
IN_VENV = getattr(sys, "real_prefix", sys.base_prefix) != sys.prefix


class OscArgumentParser(argparse.ArgumentParser):
    def _get_formatter(self):
        # cache formatter to speed things a little bit up
        if not hasattr(self, "_formatter"):
            self._formatter = self.formatter_class(prog=self.prog)
        return self._formatter

    def add_argument(self, *args, **kwargs):
        # remember added arguments so we can add them to subcommands easily
        if not hasattr(self, "_added_arguments"):
            self._added_arguments = []
        argument = super().add_argument(*args, **kwargs)
        self._added_arguments.append((argument, args, kwargs))
        return argument


class Command:
    #: Name of the command as used in the argument parser.
    name: str = None

    #: Optional aliases to the command.
    aliases: List[str] = []

    #: Whether the command is hidden from help.
    #: Defaults to ``False``.
    hidden: bool = False

    #: Name of the parent command class.
    #: Can be prefixed if the parent comes from a different location,
    #: for example ``osc.commands.<ClassName>`` when extending osc command with a plugin.
    #: See ``OscMainCommand.MODULES`` for available prefixes.
    parent: str = None

    def __init__(self, full_name, parent=None):
        self.full_name = full_name
        self.parent = parent
        self.subparsers = None

        if not self.name:
            raise ValueError(f"Command '{self.full_name}' has no 'name' set")

        if parent:
            self.parser = self.parent.subparsers.add_parser(
                self.name,
                aliases=self.aliases,
                help=self.get_help(),
                description=self.get_description(),
                formatter_class=cmdln.HelpFormatter,
                conflict_handler="resolve",
                prog=f"{self.main_command.name} [global opts] {self.name}",
            )
            self.parser.set_defaults(_selected_command=self)
        else:
            self.parser = OscArgumentParser(
                description=self.get_description(),
                formatter_class=cmdln.HelpFormatter,
                usage="%(prog)s [global opts] <command> [--help] [opts] [args]",
            )

        if self.parent:
            for arg, arg_args, arg_kwargs in self.parent.parser._added_arguments:
                if not arg_args:
                    continue
                if not arg_args[0].startswith("-"):
                    continue
                if "--help" in arg_args:
                    continue

                arg_kwargs = arg_kwargs.copy()
                arg_kwargs["help"] = argparse.SUPPRESS
                arg_kwargs["default"] = argparse.SUPPRESS
                new_arg = self.parser.add_argument(*arg_args, **arg_kwargs)
                new_arg.completer = getattr(arg, "completer", None)

        self.init_arguments()

    def __repr__(self):
        return f"<osc plugin {self.full_name} at {self.__hash__():#x}>"

    def get_help(self):
        """
        Return the help text of the command.
        The first line of the docstring is returned by default.
        """
        if self.hidden:
            return argparse.SUPPRESS

        if not self.__doc__:
            return ""

        help_lines = self.__doc__.strip().splitlines()

        if not help_lines:
            return ""

        return help_lines[0]

    def get_description(self):
        """
        Return the description of the command.
        The docstring without the first line is returned by default.
        """
        if not self.__doc__:
            return ""

        help_lines = self.__doc__.strip().splitlines()

        if not help_lines:
            return ""

        if getattr(self.main_command, "argparse_manpage", False):
            # skip the first line that contains help text
            help_lines.pop(0)

            # remove any leading empty lines
            while help_lines and not help_lines[0]:
                help_lines.pop(0)

        result = "\n".join(help_lines)
        result = textwrap.dedent(result)
        return result

    @property
    def main_command(self):
        """
        Return reference to the main command that represents the executable
        and contains the main instance of ArgumentParser.
        """
        if not self.parent:
            return self
        return self.parent.main_command

    def add_argument(self, *args, **kwargs):
        """
        Add a new argument to the command's argument parser.
        See `argparse <https://docs.python.org/3/library/argparse.html>`_ documentation for allowed parameters.
        """
        return self.parser.add_argument(*args, **kwargs)

    def init_arguments(self):
        """
        Override to add arguments to the argument parser.

        .. note::
            Make sure you're adding arguments only by calling ``self.add_argument()``.
            Using ``self.parser.add_argument()`` directly is not recommended
            because it disables argument intermixing.
        """

    def post_parse_args(self, args):
        pass

    def run(self, args):
        """
        Override to implement the command functionality.

        .. note::
            ``args.positional_args`` is a list containing any unknown (unparsed) positional arguments.

        .. note::
            Consider moving any reusable code into a library,
            leaving the command-line code only a thin wrapper on top of it.

            If the code is generic enough, it should be added to osc directly.
            In such case don't hesitate to open an `issue <https://github.com/openSUSE/osc/issues>`_.
        """
        raise NotImplementedError()

    def register(self, command_class, command_full_name):
        if not self.subparsers:
            # instantiate subparsers on first use
            self.subparsers = self.parser.add_subparsers(dest="command", title="commands")

        # Check for parser conflicts.
        # This is how Python 3.11+ behaves by default.
        if command_class.name in self.subparsers._name_parser_map:
            raise argparse.ArgumentError(self.subparsers, f"conflicting subparser: {command_class.name}")
        for alias in command_class.aliases:
            if alias in self.subparsers._name_parser_map:
                raise argparse.ArgumentError(self.subparsers, f"conflicting subparser alias: {alias}")

        command = command_class(command_full_name, parent=self)
        return command


class MainCommand(Command):
    MODULES: Tuple[Tuple[str, str]] = ()

    def __init__(self):
        super().__init__(self.__class__.__name__)
        self.command_classes = {}
        self.download_progress = None

    def post_parse_args(self, args):
        pass

    def run(self, args):
        cmd = getattr(args, "_selected_command", None)
        if not cmd:
            self.parser.error("Please specify a command")
        self.post_parse_args(args)
        cmd.post_parse_args(args)
        return cmd.run(args)

    def load_command(self, cls, module_prefix):
        mod_cls_name = f"{module_prefix}.{cls.__name__}"
        parent_name = getattr(cls, "parent", None)
        if parent_name:
            # allow relative references to classes in the the same module/directory
            if "." not in parent_name:
                parent_name = f"{module_prefix}.{parent_name}"
            try:
                parent = self.main_command.command_classes[parent_name]
            except KeyError:
                msg = f"Failed to load command class '{mod_cls_name}' because it references parent '{parent_name}' that doesn't exist"
                print(msg, file=sys.stderr)
                return None
            cmd = parent.register(cls, mod_cls_name)
        else:
            cmd = self.main_command.register(cls, mod_cls_name)

        cmd.full_name = mod_cls_name
        self.main_command.command_classes[mod_cls_name] = cmd
        return cmd

    def load_commands(self):
        if IN_VENV:
            from . import output  # pylint: disable=import-outside-toplevel
            output.print_msg("Running in virtual environment, skipping loading plugins installed outside the virtual environment.", print_to="debug")

        for module_prefix, module_path in self.MODULES:
            module_path = os.path.expanduser(module_path)

            # some plugins have their modules installed next to them instead of site-packages
            if module_path not in sys.path:
                sys.path.append(module_path)

            for loader, module_name, _ in pkgutil.iter_modules(path=[module_path]):
                full_name = f"{module_prefix}.{module_name}"
                spec = loader.find_spec(full_name)
                mod = importlib.util.module_from_spec(spec)
                try:
                    spec.loader.exec_module(mod)
                except Exception as e:  # pylint: disable=broad-except
                    msg = f"Failed to load commands from module '{full_name}': {e}"
                    print(msg, file=sys.stderr)
                    continue
                for name in dir(mod):
                    if name.startswith("_"):
                        continue
                    cls = getattr(mod, name)
                    if not inspect.isclass(cls):
                        continue
                    if not issubclass(cls, Command):
                        continue
                    if cls.__module__ != full_name:
                        # skip classes that weren't defined directly in the loaded plugin module
                        continue
                    self.load_command(cls, module_prefix)

    def enable_autocomplete(self):
        """
        The method must be called *after* the parser is populated with options and subcommands.
        """
        try:
            import argcomplete

            argcomplete.autocomplete(self.parser)
        except ImportError:
            pass

    def parse_args(self, *args, **kwargs):
        namespace, unknown_args = self.parser.parse_known_args(*args, **kwargs)

        unrecognized = [i for i in unknown_args if i.startswith("-")]
        if unrecognized:
            self.parser.error(f"unrecognized arguments: " + " ".join(unrecognized))

        namespace.positional_args = list(unknown_args)
        return namespace
