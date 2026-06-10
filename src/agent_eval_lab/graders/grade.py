"""Pure verification dispatch: VerificationSpec + trajectory turns -> GradeResult."""

from collections.abc import Mapping, Sequence
from typing import Any

from agent_eval_lab.graders.ast_tool_match import grade_tool_calls
from agent_eval_lab.graders.exact_match import grade_exact_match
from agent_eval_lab.tasks.grading import GradeResult
from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.tasks.verification import (
    OutputMatchSpec,
    ToolCallMatchSpec,
    ensure_supported,
)


def _observed_calls(turns: Sequence[Any]) -> tuple[ToolCall, ...]:
    calls: list[ToolCall] = []
    for turn in turns:
        if isinstance(turn, ToolCallTurn):
            calls.extend(turn.tool_calls)
    return tuple(calls)


def _last_assistant_text(turns: Sequence[Any]) -> str:
    texts = [t.content for t in turns if isinstance(t, MessageTurn) and t.role == "assistant"]
    return texts[-1] if texts else ""


def grade_trajectory(
    spec: Any, turns: Sequence[Any], schemas: Mapping[str, Any]
) -> GradeResult:
    """Dispatch on spec.type; reject unimplemented variants with a typed error."""
    ensure_supported(spec.type)
    if isinstance(spec, ToolCallMatchSpec):
        return grade_tool_calls(spec, _observed_calls(turns), schemas)
    if isinstance(spec, OutputMatchSpec):
        return grade_exact_match(expected=spec.expected_output, actual=_last_assistant_text(turns))
    raise AssertionError(f"unreachable spec dispatch for {spec.type!r}")
