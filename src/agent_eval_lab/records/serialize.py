"""Pure dict round-trips for records (JSONL persistence + golden suite)."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.env_health import EnvHealth
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


def _deep_to_plain(value: Any) -> Any:
    """Recursively convert Mapping → dict and list/tuple → list; scalars pass."""
    if isinstance(value, Mapping):
        return {k: _deep_to_plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_deep_to_plain(v) for v in value]
    return value


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


def env_health_to_dict(health: EnvHealth) -> dict[str, Any]:
    return {
        "pre_healthy": health.pre_healthy,
        "post_healthy": health.post_healthy,
        "pre_status": health.pre_status,
        "post_status": health.post_status,
    }


def env_health_from_dict(data: Mapping[str, Any]) -> EnvHealth:
    return EnvHealth(
        pre_healthy=data["pre_healthy"],
        post_healthy=data["post_healthy"],
        pre_status=data.get("pre_status"),
        post_status=data.get("post_status"),
    )


def trajectory_to_dict(trajectory: Trajectory) -> dict[str, Any]:
    parse_failure = trajectory.parse_failure
    d: dict[str, Any] = {
        "schema_version": trajectory.schema_version,
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
            None
            if trajectory.final_state is None
            else _deep_to_plain(trajectory.final_state)
        ),
        "rounds": trajectory.rounds,
        "wall_time_s": trajectory.wall_time_s,
        "tool_call_counts": dict(trajectory.tool_call_counts),
        "safety_cap_bound": trajectory.safety_cap_bound,
        "max_rounds": trajectory.max_rounds,
        "safety_cap": trajectory.safety_cap,
        "max_rounds_bound": trajectory.max_rounds_bound,
        "env_health": (
            None
            if trajectory.env_health is None
            else env_health_to_dict(trajectory.env_health)
        ),
        "run_uid": trajectory.run_uid,
    }
    if trajectory.max_tokens is not None:
        d["max_tokens"] = trajectory.max_tokens
    return d


def trajectory_from_dict(data: Mapping[str, Any]) -> Trajectory:
    usage_data = data.get("usage", {})
    usage = Usage(
        prompt_tokens=usage_data.get("prompt_tokens", 0),
        completion_tokens=usage_data.get("completion_tokens", 0),
        latency_s=usage_data.get("latency_s", 0.0),
    )
    turns = tuple(turn_from_dict(t) for t in data["turns"])
    pf = data.get("parse_failure")
    parse_failure = (
        None if pf is None else ParseFailure(raw=pf["raw"], error=pf["error"])
    )
    # v1-compat routing seam: an artifact with no schema_version predates the
    # records+runner revision — hydrate it via Trajectory.v1_compat so every
    # new field gets a safe default and the run is tagged schema_version="1".
    if "schema_version" not in data:
        return Trajectory.v1_compat(
            {
                "turns": turns,
                "usage": usage,
                "run_index": data.get("run_index", 0),
                "stop_reason": data.get("stop_reason", "completed"),
                "parse_failure": parse_failure,
                "final_state": data.get("final_state"),
                "max_tokens": data.get("max_tokens"),
            }
        )
    env_health = data.get("env_health")
    return Trajectory(
        turns=turns,
        usage=usage,
        run_index=data.get("run_index", 0),
        stop_reason=data.get("stop_reason", "completed"),
        schema_version=data["schema_version"],
        parse_failure=parse_failure,
        final_state=data.get("final_state"),
        max_tokens=data.get("max_tokens"),
        rounds=data.get("rounds", 0),
        wall_time_s=data.get("wall_time_s", 0.0),
        tool_call_counts=data.get("tool_call_counts", {}),
        safety_cap_bound=data.get("safety_cap_bound", False),
        max_rounds=data.get("max_rounds"),
        safety_cap=data.get("safety_cap"),
        max_rounds_bound=data.get("max_rounds_bound", False),
        env_health=(None if env_health is None else env_health_from_dict(env_health)),
        run_uid=data.get("run_uid"),
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


def verdict_to_dict(value: Any) -> dict[str, Any]:
    # The judge's legacy "verdict" tag is frozen as-is: renaming it would
    # break round-trips of existing artifacts (item 002 resolved decision 9).
    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.execution import execution_result_to_dict
    from agent_eval_lab.runners.judge_edge import JudgeError
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    if isinstance(value, JudgeVerdict):
        return {
            "type": "verdict",
            "score": value.score,
            "rationale": value.rationale,
            "raw": value.raw,
            "judge_model": value.judge_model,
            "prompt_hash": value.prompt_hash,
        }
    if isinstance(value, JudgeError):
        return {
            "type": "judge_error",
            "kind": value.kind,
            "error": value.error,
            "prompt_hash": value.prompt_hash,
            "judge_model": value.judge_model,
        }
    if isinstance(value, ExecutionVerdict):
        return {
            "type": "execution_verdict",
            "result": execution_result_to_dict(value.result),
            "execution_hash": value.execution_hash,
            "displaced_paths": list(value.displaced_paths),
        }
    if isinstance(value, ExecutionError):
        return {
            "type": "execution_error",
            "kind": value.kind,
            "detail": value.detail,
            "execution_hash": value.execution_hash,
        }
    raise ValueError(f"not a verdict value: {value!r}")


def verdict_from_dict(data: Mapping[str, Any]) -> Any:
    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.execution import execution_result_from_dict
    from agent_eval_lab.runners.judge_edge import JudgeError
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    if "type" not in data:
        raise ValueError(f"verdict dict missing required 'type' key: {data!r}")
    if data["type"] == "verdict":
        return JudgeVerdict(
            score=data["score"],
            rationale=data["rationale"],
            raw=data["raw"],
            judge_model=data["judge_model"],
            prompt_hash=data["prompt_hash"],
        )
    if data["type"] == "judge_error":
        return JudgeError(
            kind=data["kind"],
            error=data["error"],
            prompt_hash=data["prompt_hash"],
            judge_model=data["judge_model"],
        )
    if data["type"] == "execution_verdict":
        return ExecutionVerdict(
            result=execution_result_from_dict(data["result"]),
            execution_hash=data["execution_hash"],
            displaced_paths=tuple(data["displaced_paths"]),
        )
    if data["type"] == "execution_error":
        return ExecutionError(
            kind=data["kind"],
            detail=data["detail"],
            execution_hash=data["execution_hash"],
        )
    raise ValueError(f"unknown verdict value type: {data['type']!r}")
