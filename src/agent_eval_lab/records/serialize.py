"""Pure dict round-trips for records (JSONL persistence + golden suite)."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolOutcome,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)


def outcome_to_dict(outcome: ToolOutcome) -> dict[str, Any]:
    if isinstance(outcome, ToolSuccess):
        return {"type": "success", "result": outcome.result}
    return {"type": "failure", "error": outcome.error}


def outcome_from_dict(data: Mapping[str, Any]) -> ToolOutcome:
    if data["type"] == "success":
        return ToolSuccess(result=data["result"])
    if data["type"] == "failure":
        return ToolFailure(error=data["error"])
    raise ValueError(f"unknown outcome type: {data['type']!r}")


def turn_to_dict(turn: Turn) -> dict[str, Any]:
    if isinstance(turn, MessageTurn):
        return {"type": "message", "role": turn.role, "content": turn.content}
    if isinstance(turn, ToolCallTurn):
        return {
            "type": "tool_call",
            "content": turn.content,
            "tool_calls": [
                {"call_id": c.call_id, "name": c.name, "arguments": dict(c.arguments)}
                for c in turn.tool_calls
            ],
        }
    if isinstance(turn, ToolResultTurn):
        return {
            "type": "tool_result",
            "call_id": turn.call_id,
            "outcome": outcome_to_dict(turn.outcome),
        }
    raise ValueError(f"unknown turn: {turn!r}")


def turn_from_dict(data: Mapping[str, Any]) -> Turn:
    kind = data["type"]
    if kind == "message":
        return MessageTurn(role=data["role"], content=data["content"])
    if kind == "tool_call":
        calls = tuple(
            ToolCall(call_id=c["call_id"], name=c["name"], arguments=c["arguments"])
            for c in data["tool_calls"]
        )
        return ToolCallTurn(tool_calls=calls, content=data.get("content"))
    if kind == "tool_result":
        return ToolResultTurn(
            call_id=data["call_id"], outcome=outcome_from_dict(data["outcome"])
        )
    raise ValueError(f"unknown turn type: {kind!r}")


def trajectory_to_dict(trajectory: Trajectory) -> dict[str, Any]:
    parse_failure = trajectory.parse_failure
    return {
        "turns": [turn_to_dict(t) for t in trajectory.turns],
        "usage": {
            "prompt_tokens": trajectory.usage.prompt_tokens,
            "completion_tokens": trajectory.usage.completion_tokens,
            "latency_s": trajectory.usage.latency_s,
        },
        "run_index": trajectory.run_index,
        "stop_reason": trajectory.stop_reason,
        "parse_failure": (
            None
            if parse_failure is None
            else {"raw": parse_failure.raw, "error": parse_failure.error}
        ),
        "final_state": (
            None if trajectory.final_state is None else dict(trajectory.final_state)
        ),
    }


def trajectory_from_dict(data: Mapping[str, Any]) -> Trajectory:
    usage = data.get("usage", {})
    parse_failure = data.get("parse_failure")
    return Trajectory(
        turns=tuple(turn_from_dict(t) for t in data["turns"]),
        usage=Usage(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            latency_s=usage.get("latency_s", 0.0),
        ),
        run_index=data.get("run_index", 0),
        stop_reason=data.get("stop_reason", "completed"),
        parse_failure=(
            None
            if parse_failure is None
            else ParseFailure(raw=parse_failure["raw"], error=parse_failure["error"])
        ),
        final_state=data.get("final_state"),
    )


def grade_result_to_dict(grade: GradeResult) -> dict[str, Any]:
    return {
        "grader_id": grade.grader_id,
        "passed": grade.passed,
        "score": grade.score,
        "evidence": dict(grade.evidence),
        "failure_reason": grade.failure_reason,
    }


def run_result_to_dict(run: RunResult) -> dict[str, Any]:
    return {
        "task_id": run.task_id,
        "condition_id": run.condition_id,
        "run_index": run.run_index,
        "trajectory": trajectory_to_dict(run.trajectory),
        "grade": grade_result_to_dict(run.grade),
    }
