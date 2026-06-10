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
        raw_arguments = function.get("arguments") or "{}"
        try:
            arguments = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            return ParseFailure(
                raw=raw_arguments, error=f"arguments not valid JSON: {exc}"
            )
        if not isinstance(arguments, dict):
            return ParseFailure(
                raw=raw_arguments, error="arguments must be a JSON object"
            )
        calls.append(
            ToolCall(
                call_id=raw.get("id", f"call-{index}"), name=name, arguments=arguments
            )
        )
    return ToolCallTurn(tool_calls=tuple(calls), content=content)
