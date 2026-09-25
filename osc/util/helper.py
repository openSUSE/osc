# Copyright (C) 2018 SUSE Linux.  All rights reserved.
# This program is free software; it may be used, copied, modified
# and distributed under the terms of the GNU General Public Licence,
# either version 2, or (at your option) any later version.


import builtins
import html

from .. import oscerr


def decode_list(ilist):
    """ Decodes the elements of a list if needed
    """

    dlist = []
    for elem in ilist:
        if not isinstance(elem, str):
            dlist.append(decode_it(elem))
        else:
            dlist.append(elem)
    return dlist


def decode_it(obj):
    """Decode the given object unless it is a str.

    If the given object is a str or has no decode method, the object itself is
    returned. Otherwise, try to decode the object using utf-8. If this
    fails due to a UnicodeDecodeError, try to decode the object using
    latin-1.
    """
    if isinstance(obj, str) or not hasattr(obj, 'decode'):
        return obj
    try:
        return obj.decode('utf-8')
    except UnicodeDecodeError:
        return obj.decode('latin-1')


def _is_non_interactive():
    # The effective flag lives in the resolved configuration (oscrc,
    # OSC_NON_INTERACTIVE, --setopt, --non-interactive); importing conf
    # lazily keeps this module free of import cycles (conf imports
    # raw_input from here).
    from .. import conf

    return conf.config["non_interactive"]


def is_non_interactive():
    """
    Return True when running in non-interactive mode.

    For call sites that need to branch on the mode themselves; most call
    sites should use the require_*/refuse_* helpers or raw_input() instead.
    """
    return _is_non_interactive()


def raise_non_interactive(prompt, hint=None):
    """
    Raise oscerr.NonInteractiveInput for a prompt that cannot be answered
    in non-interactive mode.
    """
    msg = f"input requested in non-interactive mode: {prompt!r}."
    if hint:
        msg += f" {hint}"
    raise oscerr.NonInteractiveInput(msg)


def require_non_interactive_options(command, requirements):
    """
    Pre-flight check for --non-interactive: fail before the command does any
    work unless every option needed to answer its prompts was passed on the
    command line. All missing options are named at once. Does nothing when
    running interactively.

    :param command: command description, e.g. "osc request accept"
    :param requirements: iterable of (value, option_spelling) pairs; an option
        counts as missing when its value is falsy
    """
    if not _is_non_interactive():
        return
    missing = [spelling for value, spelling in requirements if not value]
    if missing:
        raise_non_interactive(
            f"prompts for {command} cannot be answered",
            hint=f"Pass {' and '.join(missing)} to answer every prompt upfront.",
        )


def require_any_non_interactive_options(command, requirements):
    """
    Pre-flight check for --non-interactive: fail before the command does any
    work unless at least one of the options needed to answer its prompts was
    passed on the command line. Does nothing when running interactively.

    :param command: command description, e.g. "osc commit"
    :param requirements: iterable of (value, option_spelling) pairs; an option
        counts as given when its value is truthy
    """
    if not _is_non_interactive():
        return
    if not any(value for value, _spelling in requirements):
        spellings = " or ".join(spelling for _value, spelling in requirements)
        raise_non_interactive(
            f"prompts for {command} cannot be answered",
            hint=f"Pass {spellings} to answer the prompt upfront.",
        )


def refuse_non_interactive(reason, hint=None):
    """
    Pre-flight check for --non-interactive: refuse a command (or flag
    combination) that is inherently interactive and cannot run without
    prompting. Does nothing when running interactively.

    :param hint: names what to do instead; every refusal must explain the
        alternative (or its absence) specifically. Required: omitting it
        is a TypeError.
    """
    if hint is None:
        raise TypeError("refuse_non_interactive() requires a hint naming the alternative")
    if _is_non_interactive():
        raise_non_interactive(reason, hint=hint)


def raw_input(*args, hint=None, default=None):
    """
    Read a line from stdin, like builtins.input().

    In non-interactive mode (conf.config["non_interactive"]) return
    ``default`` without prompting; raise oscerr.NonInteractiveInput when
    there is no default to fall back to. ``hint`` names the option that
    answers the prompt and is included in the error.
    """
    if _is_non_interactive():
        if default is not None:
            # behave as if the user pressed Enter: the documented default
            # (the capitalized letter in y/N or Y/n prompts) applies
            return default
        prompt = args[0] if args else ""
        raise_non_interactive(prompt, hint=hint)
    func = builtins.input

    try:
        return func(*args)
    except EOFError:
        # interpret ctrl-d as user abort
        raise oscerr.UserAbort()


def _html_escape(data):
    return html.escape(data, quote=False)


def format_table(rows, headers):
    """Format list of tuples into equal width table with headers"""
    maxlens = [len(h) for h in headers]
    for r in rows:
        for i, c in enumerate(r):
            maxlens[i] = max(maxlens[i], len(c))
    tpltpl = []
    for i, m in enumerate(maxlens):
        tpltpl.append('{%s:<%s}' % (i, m))
    # {0:12}  {1:7}  {2:10}  {3:8}
    templ = '  '.join(tpltpl) + '\n'

    out = templ.format(*headers)
    out += templ.format(*['-' * m for m in maxlens])
    for r in rows:
        out += templ.format(*r)
    return out
