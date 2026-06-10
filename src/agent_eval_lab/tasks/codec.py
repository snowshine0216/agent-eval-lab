"""Pure to_dict/from_dict for every record. Tagged unions dispatch on `type`."""

from typing import Any

from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec

_TURN_BY_TAG = {
    "message": MessageTurn,
    "tool_call": ToolCallTurn,
    "tool_result": ToolResultTurn,
}
_OUTCOME_BY_TAG = {"success": ToolSuccess, "failure": ToolFailure}
_VERIFY_BY_TAG = {"output_match": OutputMatchSpec, "tool_call_match": ToolCallMatchSpec}


def _call_to_dict(c: ToolCall | ExpectedToolCall) -> dict[str, Any]:
    out = {"name": c.name, "arguments": dict(c.arguments)}
    if isinstance(c, ToolCall):
        out["call_id"] = c.call_id
        if c.arguments_parse_error is not None:
            out["arguments_parse_error"] = c.arguments_parse_error
    return out


def _turn_to_dict(t: Any) -> dict[str, Any]:
    if isinstance(t, MessageTurn):
        return {"type": "message", "role": t.role, "content": t.content}
    if isinstance(t, ToolCallTurn):
        return {
            "type": "tool_call",
            "content": t.content,
            "tool_calls": [_call_to_dict(c) for c in t.tool_calls],
        }
    outcome = t.outcome
    tag = "success" if isinstance(outcome, ToolSuccess) else "failure"
    body = {"result": outcome.result} if tag == "success" else {"error": outcome.error}
    return {
        "type": "tool_result",
        "call_id": t.call_id,
        "outcome": {"type": tag, **body},
    }


def _verify_to_dict(v: Any) -> dict[str, Any]:
    if isinstance(v, OutputMatchSpec):
        return {
            "type": "output_match",
            "expected_output": v.expected_output,
            "normalizer": v.normalizer,
        }
    return {
        "type": "tool_call_match",
        "match": v.match,
        "expected_tool_calls": [_call_to_dict(c) for c in v.expected_tool_calls],
    }


def to_dict(record: Any) -> dict[str, Any]:
    """Serialize any locked record to a plain JSON-able dict."""
    if isinstance(record, (ToolCall, ExpectedToolCall)):
        return _call_to_dict(record)
    if isinstance(record, (MessageTurn, ToolCallTurn, ToolResultTurn)):
        return _turn_to_dict(record)
    if isinstance(record, (OutputMatchSpec, ToolCallMatchSpec)):
        return _verify_to_dict(record)
    if isinstance(record, TaskInput):
        return {
            "messages": [_turn_to_dict(m) for m in record.messages],
            "available_tools": [dict(s) for s in record.available_tools],
        }
    if isinstance(record, TaskMetadata):
        return {
            "split": record.split,
            "version": record.version,
            "provenance": record.provenance,
            "world_template_id": record.world_template_id,
            "difficulty_knob": record.difficulty_knob,
        }
    if isinstance(record, Task):
        return {
            "id": record.id,
            "capability": record.capability,
            "input": to_dict(record.input),
            "verification": _verify_to_dict(record.verification),
            "metadata": to_dict(record.metadata),
            "initial_state": dict(record.initial_state)
            if record.initial_state is not None
            else None,
        }
    if isinstance(record, GradeResult):
        return {
            "grader_id": record.grader_id,
            "passed": record.passed,
            "score": record.score,
            "evidence": dict(record.evidence),
            "failure_reason": record.failure_reason,
        }
    if isinstance(record, Trajectory):
        return {
            "turns": [_turn_to_dict(t) for t in record.turns],
            "usage": dict(record.usage),
            "cost_usd": record.cost_usd,
            "latency_ms": record.latency_ms,
            "run_index": record.run_index,
            "termination_reason": record.termination_reason,
        }
    if isinstance(record, RunResult):
        return {
            "task_id": record.task_id,
            "condition_id": record.condition_id,
            "run_index": record.run_index,
            "trajectory": to_dict(record.trajectory),
            "grade": to_dict(record.grade),
        }
    raise TypeError(f"cannot serialize {type(record).__name__}")


def _call_from_dict(cls: Any, d: dict[str, Any]) -> Any:
    if cls is ToolCall:
        return ToolCall(
            call_id=d["call_id"],
            name=d["name"],
            arguments=dict(d.get("arguments", {})),
            arguments_parse_error=d.get("arguments_parse_error"),
        )
    return ExpectedToolCall(name=d["name"], arguments=dict(d.get("arguments", {})))


def _turn_from_dict(d: dict[str, Any]) -> Any:
    cls = _TURN_BY_TAG[d["type"]]
    if cls is MessageTurn:
        return MessageTurn(role=d["role"], content=d["content"])
    if cls is ToolCallTurn:
        return ToolCallTurn(
            content=d.get("content"),
            tool_calls=tuple(_call_from_dict(ToolCall, c) for c in d["tool_calls"]),
        )
    o = d["outcome"]
    outcome = (
        ToolSuccess(result=o["result"])
        if o["type"] == "success"
        else ToolFailure(error=o["error"])
    )
    return ToolResultTurn(call_id=d["call_id"], outcome=outcome)


def _verify_from_dict(d: dict[str, Any]) -> Any:
    cls = _VERIFY_BY_TAG[d["type"]]
    if cls is OutputMatchSpec:
        return OutputMatchSpec(
            expected_output=d["expected_output"], normalizer=d.get("normalizer")
        )
    return ToolCallMatchSpec(
        match=d.get("match", "exact_sequence"),
        expected_tool_calls=tuple(
            _call_from_dict(ExpectedToolCall, c) for c in d["expected_tool_calls"]
        ),
    )


def from_dict(cls: Any, d: dict[str, Any]) -> Any:
    """Deserialize a plain dict back into the given record class."""
    if cls in (ToolCall, ExpectedToolCall):
        return _call_from_dict(cls, d)
    if cls in (MessageTurn, ToolCallTurn, ToolResultTurn):
        return _turn_from_dict(d)
    if cls in (OutputMatchSpec, ToolCallMatchSpec):
        return _verify_from_dict(d)
    if cls is TaskInput:
        return TaskInput(
            messages=tuple(_turn_from_dict(m) for m in d["messages"]),
            available_tools=tuple(dict(s) for s in d["available_tools"]),
        )
    if cls is TaskMetadata:
        return TaskMetadata(**d)
    if cls is Task:
        return Task(
            id=d["id"],
            capability=d["capability"],
            input=from_dict(TaskInput, d["input"]),
            verification=_verify_from_dict(d["verification"]),
            metadata=from_dict(TaskMetadata, d["metadata"]),
            initial_state=dict(d["initial_state"])
            if d.get("initial_state") is not None
            else None,
        )
    if cls is GradeResult:
        return GradeResult(
            grader_id=d["grader_id"],
            passed=d["passed"],
            score=d["score"],
            evidence=dict(d.get("evidence", {})),
            failure_reason=d.get("failure_reason"),
        )
    if cls is Trajectory:
        return Trajectory(
            turns=tuple(_turn_from_dict(t) for t in d["turns"]),
            usage=dict(d["usage"]),
            cost_usd=d["cost_usd"],
            latency_ms=d["latency_ms"],
            run_index=d["run_index"],
            termination_reason=d["termination_reason"],
        )
    if cls is RunResult:
        return RunResult(
            task_id=d["task_id"],
            condition_id=d["condition_id"],
            run_index=d["run_index"],
            trajectory=from_dict(Trajectory, d["trajectory"]),
            grade=from_dict(GradeResult, d["grade"]),
        )
    raise TypeError(f"cannot deserialize {getattr(cls, '__name__', cls)}")
