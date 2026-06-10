"""Pure conversions between Turn records and the OpenAI wire format."""

import json
from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)
from agent_eval_lab.tools.workspace import ToolDef


def tooldef_to_openai(tool: ToolDef) -> Mapping[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        },
    }


def turn_to_message(turn: Turn) -> Mapping[str, Any]:
    if isinstance(turn, MessageTurn):
        return {"role": turn.role, "content": turn.content}
    if isinstance(turn, ToolCallTurn):
        # OpenAI wire format requires tool-call messages be attributed to "assistant".
        return {
            "role": "assistant",
            "content": turn.content,
            "tool_calls": [
                {
                    "id": call.call_id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": json.dumps(dict(call.arguments), sort_keys=True),
                    },
                }
                for call in turn.tool_calls
            ],
        }
    if isinstance(turn, ToolResultTurn):
        content = (
            json.dumps(turn.outcome.result)
            if isinstance(turn.outcome, ToolSuccess)
            else json.dumps({"error": turn.outcome.error})
        )
        return {"role": "tool", "tool_call_id": turn.call_id, "content": content}
    raise ValueError(f"unknown turn: {turn!r}")
