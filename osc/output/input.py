import sys
import textwrap
from typing import Dict
from typing import Optional

from .. import oscerr
from .tty import colorize


def get_user_input(question: str, answers: Dict[str, str], default_answer: Optional[str] = None) -> str:
    """
    Ask user a question and wait for reply.

    :param question: The question. The text gets automatically dedented and stripped.
    :param answers: A dictionary with answers. Keys are the expected replies and values are their descriptions.
    :param default_answer: The default answer. Must be ``None`` or match an ``answers`` entry.
    """

    if default_answer and default_answer not in answers:
        raise ValueError(f"Default answer doesn't match any answer: {default_answer}")

    question = textwrap.dedent(question)
    question = question.strip()

    prompt = []
    for key, value in answers.items():
        value = f"{colorize(key, 'bold')}){value}"
        prompt.append(value)

    prompt_str = " / ".join(prompt)
    if default_answer:
        prompt_str += f" (default={colorize(default_answer, 'bold')})"
    prompt_str += ": "

    print(question, file=sys.stderr)

    while True:
        try:
            reply = input(prompt_str)
        except EOFError:
            # interpret ctrl-d as user abort
            raise oscerr.UserAbort()  # pylint: disable=raise-missing-from

        if reply in answers:
            return reply
        if reply.strip() in answers:
            return reply.strip()
        if not reply.strip():
            return default_answer

        print(f"Invalid reply: {colorize(reply, 'bold,red')}", file=sys.stderr)
