import sys
import textwrap
from typing import Dict
from typing import Optional

from ..util.helper import raw_input
from .tty import colorize


def get_user_input(
    question: str,
    answers: Dict[str, str],
    default_answer: Optional[str] = None,
    vertical: bool = False,
    hint: Optional[str] = None,
) -> str:
    """
    Ask user a question and wait for reply.

    :param question: The question. The text gets automatically dedented and stripped.
    :param answers: A dictionary with answers. Keys are the expected replies and values are their descriptions.
    :param default_answer: The default answer. Must be ``None`` or match an ``answers`` entry.
    :param hint: Hint naming the option that answers the question; used when refusing to prompt in non-interactive mode.
    :return: the chosen answer, or the default answer in non-interactive mode.
    """

    if default_answer and default_answer not in answers:
        raise ValueError(f"Default answer doesn't match any answer: {default_answer}")

    from .. import conf

    if conf.config["non_interactive"]:
        # behave as if the user pressed Enter: the default answer applies
        # (no prompt is shown and no input is read)
        return default_answer

    question = textwrap.dedent(question)
    question = question.strip()

    prompt = []
    for key, value in answers.items():
        value = f"{colorize(key, 'bold')}){value}"
        prompt.append(value)

    if vertical:
        prompt_str = "\n".join(prompt)
        if default_answer:
            prompt_str += f"\n(default={colorize(default_answer, 'bold')})"
        prompt_str += "\n"
        prompt_str += question + " "
    else:
        prompt_str = " / ".join(prompt)
        if default_answer:
            prompt_str += f" (default={colorize(default_answer, 'bold')})"
        prompt_str += "\n"
        prompt_str += question + " "

    while True:
        # raises UserAbort on EOF and NonInteractiveInput in non-interactive mode
        reply = raw_input(prompt_str, hint=hint)

        if reply in answers:
            return reply
        if reply.strip() in answers:
            return reply.strip()
        if not reply.strip():
            return default_answer

        print(f"Invalid reply: {colorize(reply, 'bold,red')}", file=sys.stderr)
