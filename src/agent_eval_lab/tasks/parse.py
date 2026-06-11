"""Pure parsing: JSON-shaped dicts -> Task records."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.serialize import turn_from_dict
from agent_eval_lab.records.turns import MessageTurn, Turn
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExecutionSpec,
    ExpectedToolCall,
    FinalStateSpec,
    LlmJudgeSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateConstraint,
    StateContains,
    StateEquals,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    TrajectoryConstraint,
    TrajectorySpec,
    VerificationSpec,
)
from agent_eval_lab.tools.code_world import path_error, prefix_collision

_SPLITS = ("dev", "held_out")
_MATCH_MODES = ("exact_sequence", "multiset")


def _parse_scale(raw: Any) -> tuple[int, int]:
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        raise ValueError(f"scale must be a 2-element list, got {raw!r}")
    lo, hi = raw
    if (
        not (isinstance(lo, int) and isinstance(hi, int))
        or isinstance(lo, bool)
        or isinstance(hi, bool)
    ):
        raise ValueError(f"scale bounds must be ints, got {raw!r}")
    if lo >= hi:
        raise ValueError(f"scale must have lo < hi, got {raw!r}")
    return (lo, hi)


def _parse_timeout(raw: Any) -> float | None:
    """Accept a JSON int or float, store as float; bool and <= 0 are rejected."""
    if raw is None:
        return None
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ValueError(f"timeout_s must be a number, got {raw!r}")
    if raw <= 0:
        raise ValueError(f"timeout_s must be positive, got {raw!r}")
    return float(raw)


def _oracle_collision(paths: tuple[str, ...]) -> tuple[str, str] | None:
    """First oracle-internal canonical-prefix collision (001's invariant)."""
    return next(
        (
            (path_a, path_b)
            for i, path_a in enumerate(paths)
            for path_b in paths[i + 1 :]
            if prefix_collision(path_a, path_b)
        ),
        None,
    )


def _parse_held_out_tests(raw: Any) -> dict[str, str]:
    if not isinstance(raw, Mapping) or not raw:
        raise ValueError(
            f"held_out_tests must be a non-empty path->content mapping, got {raw!r}"
        )
    for path in raw:
        error = path_error(path)
        if error is not None:
            raise ValueError(f"held_out_tests: {error}")
    collision = _oracle_collision(tuple(sorted(raw)))
    if collision is not None:
        raise ValueError(
            "held_out_tests: canonical-prefix collision between "
            f"{collision[0]!r} and {collision[1]!r}"
        )
    return dict(raw)


def _state_constraint_from_dict(data: Mapping[str, Any]) -> StateConstraint:
    kind = data["type"]
    if kind == "state_equals":
        return StateEquals(path=data["path"], expected=data["expected"])
    if kind == "state_contains":
        return StateContains(path=data["path"], expected=data["expected"])
    raise ValueError(f"unknown state constraint: {kind!r}")


def _trajectory_constraint_from_dict(data: Mapping[str, Any]) -> TrajectoryConstraint:
    kind = data["type"]
    if kind == "no_tool_call":
        return NoToolCall(name=data["name"])
    if kind == "only_modifies":
        return OnlyModifies(paths=tuple(data["paths"]))
    if kind == "max_tool_calls":
        return MaxToolCalls(n=data["n"])
    raise ValueError(f"unknown trajectory constraint: {kind!r}")


def verification_from_dict(data: Mapping[str, Any]) -> VerificationSpec:
    kind = data["type"]
    if kind == "output_match":
        return OutputMatchSpec(
            expected_output=data["expected_output"],
            normalizer=data.get("normalizer"),
        )
    if kind == "tool_call_match":
        match = data.get("match", "exact_sequence")
        if match not in _MATCH_MODES:
            raise ValueError(f"unknown match mode: {match!r}")
        return ToolCallMatchSpec(
            expected_tool_calls=tuple(
                ExpectedToolCall(name=c["name"], arguments=c["arguments"])
                for c in data["expected_tool_calls"]
            ),
            match=match,
        )
    if kind == "final_state":
        return FinalStateSpec(
            constraints=tuple(
                _state_constraint_from_dict(c) for c in data["constraints"]
            )
        )
    if kind == "trajectory":
        return TrajectorySpec(
            constraints=tuple(
                _trajectory_constraint_from_dict(c) for c in data["constraints"]
            )
        )
    if kind == "all_of":
        return AllOf(specs=tuple(verification_from_dict(s) for s in data["specs"]))
    if kind == "llm_judge":
        return LlmJudgeSpec(
            rubric=data["rubric"],
            judge_model=data["judge_model"],
            scale=_parse_scale(data.get("scale", [1, 5])),
        )
    if kind == "execution":
        return ExecutionSpec(
            held_out_tests=_parse_held_out_tests(data["held_out_tests"]),
            timeout_s=_parse_timeout(data.get("timeout_s")),
        )
    raise ValueError(f"unknown verification type: {kind!r}")


def _require_message(turn: Turn) -> MessageTurn:
    if not isinstance(turn, MessageTurn):
        raise ValueError(f"task input turns must be message turns, got {turn.type!r}")
    return turn


def _parse_messages(raw: list[Mapping[str, Any]]) -> tuple[MessageTurn, ...]:
    return tuple(_require_message(turn_from_dict(m)) for m in raw)


def _parse_metadata(data: Mapping[str, Any]) -> TaskMetadata:
    if data["split"] not in _SPLITS:
        raise ValueError(f"unknown split: {data['split']!r}")
    return TaskMetadata(
        split=data["split"],
        version=data["version"],
        provenance=data["provenance"],
        world_template_id=data.get("world_template_id"),
        difficulty_knob=data.get("difficulty_knob"),
        max_steps=data.get("max_steps"),
        review=data.get("review"),
    )


def parse_task(data: Mapping[str, Any]) -> Task:
    input_data = data["input"]
    return Task(
        id=data["id"],
        capability=data["capability"],
        input=TaskInput(
            messages=_parse_messages(input_data["messages"]),
            available_tools=tuple(input_data["available_tools"]),
        ),
        verification=verification_from_dict(data["verification"]),
        metadata=_parse_metadata(data["metadata"]),
        initial_state=data.get("initial_state"),
    )
