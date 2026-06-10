"""Turns + tool outcomes — tagged unions with explicit discriminators (design §4.2)."""

from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.tasks.tool_calls import ToolCall


@dataclass(frozen=True, kw_only=True)
class MessageTurn:
    role: Literal["system", "user", "assistant"]
    content: str
    type: Literal["message"] = "message"


@dataclass(frozen=True, kw_only=True)
class ToolCallTurn:
    tool_calls: tuple[ToolCall, ...]
    content: str | None = None
    type: Literal["tool_call"] = "tool_call"


@dataclass(frozen=True, kw_only=True)
class ToolSuccess:
    result: Any
    type: Literal["success"] = "success"


@dataclass(frozen=True, kw_only=True)
class ToolFailure:
    error: str
    type: Literal["failure"] = "failure"


ToolOutcome = ToolSuccess | ToolFailure


@dataclass(frozen=True, kw_only=True)
class ToolResultTurn:
    call_id: str
    outcome: ToolOutcome
    type: Literal["tool_result"] = "tool_result"


Turn = MessageTurn | ToolCallTurn | ToolResultTurn
