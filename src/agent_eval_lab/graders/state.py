"""Pure FinalStateSpec interpreter: dot-path walk over world-state (spec §6).

Missing paths and non-mapping intermediates degrade to a _MISSING sentinel that
fails the constraint and never raises — the executable form of "distinguish
agent failures from harness failures".
"""

from collections.abc import Mapping
from typing import Any, Final

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import (
    FinalStateSpec,
    StateConstraint,
    StateEquals,
)

GRADER_ID = "final_state"


class _Missing:
    """Singleton sentinel for an unresolvable dot-path."""

    __slots__ = ()

    def __repr__(self) -> str:
        return "<MISSING>"


_MISSING: Final = _Missing()


def resolve_path(state: Mapping[str, Any] | None, path: str) -> Any:
    """Walk `state` segment-by-segment; return _MISSING on any miss. Never raises."""
    current: Any = state
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return _MISSING
        current = current[segment]
    return current


def _contains(haystack: Any, needle: Any) -> bool:
    """Membership test that fails (never raises) on a non-container haystack."""
    if isinstance(haystack, (str, bytes, Mapping)) or hasattr(haystack, "__iter__"):
        try:
            return needle in haystack
        except TypeError:
            return False
    return False


def grade_state_constraint(
    constraint: StateConstraint, state: Mapping[str, Any] | None
) -> bool:
    """Pure constraint check; True iff satisfied. Never raises."""
    value = resolve_path(state, constraint.path)
    if value is _MISSING:
        return False
    if isinstance(constraint, StateEquals):
        return value == constraint.expected
    return _contains(value, constraint.expected)


def _evidence_value(value: Any) -> Any:
    return None if value is _MISSING else value


def grade_final_state(
    *,
    spec: FinalStateSpec,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
) -> GradeResult:
    """Grade a FinalStateSpec; a constraint miss carries failure_reason=None."""
    state = trajectory.final_state
    results = tuple(
        {
            "path": c.path,
            "type": c.type,
            "expected": c.expected,
            "actual": _evidence_value(resolve_path(state, c.path)),
            "passed": grade_state_constraint(c, state),
        }
        for c in spec.constraints
    )
    passed = all(r["passed"] for r in results)
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"constraints": results},
        failure_reason=None,
    )
