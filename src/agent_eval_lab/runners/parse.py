"""Pure parsing of OpenAI-compatible assistant messages into Turn records.

Parse failures here are what the grader later reports as malformed_call.
"""

import json
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.trajectory import ParseFailure
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn


def parse_assistant_payload(
    message: Mapping[str, Any],
) -> MessageTurn | ToolCallTurn | ParseFailure:
    tool_calls = message.get("tool_calls")
    if tool_calls:
        return _parse_tool_calls(tool_calls, message.get("content"))
    content = message.get("content")
    if content is None:
        return ParseFailure(
            raw=json.dumps(dict(message)),
            error="assistant message has neither content nor tool_calls",
        )
    return MessageTurn(role="assistant", content=content)


def _parse_arguments(raw: Any) -> dict[str, Any] | ParseFailure:
    """Decode tool-call arguments without ever raising.

    Some providers send arguments already decoded as a JSON object (a dialect
    quirk, absorbed here value-for-value); the OpenAI wire format sends a JSON
    string. Anything else is recorded as a parse failure, never a crash.
    """
    if raw is None or raw == "":
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    if not isinstance(raw, str):
        return ParseFailure(
            raw=repr(raw),
            error=f"arguments have unsupported type: {type(raw).__name__}",
        )
    try:
        decoded = json.loads(raw)
    except json.JSONDecodeError as exc:
        return ParseFailure(raw=raw, error=f"arguments not valid JSON: {exc}")
    if not isinstance(decoded, dict):
        return ParseFailure(raw=raw, error="arguments must be a JSON object")
    return decoded


def _parse_tool_calls(
    raw_calls: list[Mapping[str, Any]], content: str | None
) -> ToolCallTurn | ParseFailure:
    calls: list[ToolCall] = []
    for index, raw in enumerate(raw_calls):
        function = raw.get("function", {})
        name = function.get("name")
        if not name:
            return ParseFailure(
                raw=json.dumps(dict(raw)), error="tool call missing function name"
            )
        arguments = _parse_arguments(function.get("arguments"))
        if isinstance(arguments, ParseFailure):
            return arguments
        calls.append(
            ToolCall(
                call_id=raw.get("id", f"call-{index}"), name=name, arguments=arguments
            )
        )
    return ToolCallTurn(tool_calls=tuple(calls), content=content)
