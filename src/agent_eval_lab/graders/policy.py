"""Pure TrajectorySpec interpreter: policy grading over the run (spec §6).

NoToolCall / OnlyModifies breaches are forbidden_action; MaxToolCalls breaches
are step_limit_exceeded. All checks are pure functions of
(spec, initial_state, trajectory) and never raise.
"""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.grade import FailureCategory, GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCallTurn
from agent_eval_lab.tasks.schema import (
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    TrajectoryConstraint,
    TrajectorySpec,
)

GRADER_ID = "trajectory_policy"


def _all_calls(trajectory: Trajectory) -> tuple[Any, ...]:
    return tuple(
        call
        for turn in trajectory.turns
        if isinstance(turn, ToolCallTurn)
        for call in turn.tool_calls
    )


def _check_no_tool_call(
    constraint: NoToolCall, trajectory: Trajectory
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    hit = any(call.name == constraint.name for call in _all_calls(trajectory))
    if hit:
        return False, "forbidden_action", {"forbidden_tool": constraint.name}
    return True, None, {"forbidden_tool": constraint.name}


def _check_max_tool_calls(
    constraint: MaxToolCalls, trajectory: Trajectory
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    count = len(_all_calls(trajectory))
    evidence = {"limit": constraint.n, "observed": count}
    if count > constraint.n:
        return False, "step_limit_exceeded", evidence
    return True, None, evidence


def _leaf_paths(state: Any, prefix: str = "") -> dict[str, Any]:
    """Flatten a nested mapping into {dot_path: leaf_value}. Non-mappings are leaves.

    Empty mappings contribute no leaves at any depth (consistent root/nested
    behaviour). Blind spot: creation or deletion of an *empty* container is
    invisible to leaf-diff (e.g. {} → {"tickets": {}} detects no change).
    """
    if not isinstance(state, Mapping):
        return {prefix: state} if prefix else {}
    leaves: dict[str, Any] = {}
    for key, value in state.items():
        child_prefix = f"{prefix}.{key}" if prefix else str(key)
        leaves.update(_leaf_paths(value, child_prefix))
    return leaves


def _changed_leaf_paths(
    before: Mapping[str, Any] | None, after: Mapping[str, Any] | None
) -> set[str]:
    """Set of leaf dot-paths whose value was added, removed, or changed."""
    before_leaves = _leaf_paths(before or {})
    after_leaves = _leaf_paths(after or {})
    keys = set(before_leaves) | set(after_leaves)
    sentinel = object()
    return {
        key
        for key in keys
        if before_leaves.get(key, sentinel) != after_leaves.get(key, sentinel)
    }


def _is_covered(changed: str, allowed: tuple[str, ...]) -> bool:
    """True iff a declared path equals or is a dot-segment prefix of `changed`."""
    segments = changed.split(".")
    for path in allowed:
        path_segments = path.split(".")
        if segments[: len(path_segments)] == path_segments:
            return True
    return False


def _check_only_modifies(
    constraint: OnlyModifies,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    changed = _changed_leaf_paths(initial_state, trajectory.final_state)
    violations = sorted(
        path for path in changed if not _is_covered(path, constraint.paths)
    )
    evidence = {
        "allowed": list(constraint.paths),
        "changed": sorted(changed),
        "violations": violations,
    }
    if violations:
        return False, "forbidden_action", evidence
    return True, None, evidence


def _check_constraint(
    constraint: TrajectoryConstraint,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> tuple[bool, FailureCategory | None, dict[str, Any]]:
    if isinstance(constraint, NoToolCall):
        return _check_no_tool_call(constraint, trajectory)
    if isinstance(constraint, MaxToolCalls):
        return _check_max_tool_calls(constraint, trajectory)
    return _check_only_modifies(constraint, initial_state, trajectory)


def grade_trajectory_spec(
    *,
    spec: TrajectorySpec,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> GradeResult:
    """Grade a TrajectorySpec; first failing constraint sets failure_reason."""
    checks = tuple(
        (constraint, _check_constraint(constraint, initial_state, trajectory))
        for constraint in spec.constraints
    )
    passed = all(ok for _, (ok, _, _) in checks)
    first_failure = next((reason for _, (ok, reason, _) in checks if not ok), None)
    evidence = {
        "constraints": [
            {"type": c.type, "passed": ok, **info} for c, (ok, _, info) in checks
        ]
    }
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence=evidence,
        failure_reason=first_failure,
    )
