"""Pure system-prompt override (item 004's only varying config input).

The default config passes prompt=None and the messages are returned untouched.
Non-mutating: builds a new tuple via slicing/spread, never edits in place.
"""

from agent_eval_lab.records.turns import MessageTurn, Turn


def apply_system_prompt(
    messages: tuple[Turn, ...], prompt: str | None
) -> tuple[Turn, ...]:
    """Return a new message tuple with the leading system turn's content replaced
    by `prompt` (or a new system turn prepended if there is none). `prompt=None`
    returns `messages` unchanged."""
    if prompt is None:
        return messages
    if (
        messages
        and isinstance(messages[0], MessageTurn)
        and messages[0].role == "system"
    ):
        return (MessageTurn(role="system", content=prompt), *messages[1:])
    return (MessageTurn(role="system", content=prompt), *messages)
