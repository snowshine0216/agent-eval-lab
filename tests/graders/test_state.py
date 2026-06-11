from agent_eval_lab.graders.state import (
    _MISSING,
    grade_final_state,
    grade_state_constraint,
    resolve_path,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import FinalStateSpec, StateContains, StateEquals


def test_resolve_path_walks_nested_mappings() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}

    assert resolve_path(state, "tickets.T-1.status") == "closed"


def test_resolve_path_missing_key_yields_sentinel() -> None:
    state = {"tickets": {}}

    assert resolve_path(state, "tickets.T-9.status") is _MISSING


def test_resolve_path_non_mapping_intermediate_yields_sentinel() -> None:
    state = {"tickets": {"T-1": "not-a-mapping"}}

    assert resolve_path(state, "tickets.T-1.status") is _MISSING


def test_resolve_path_over_none_state_yields_sentinel() -> None:
    assert resolve_path(None, "tickets.T-1") is _MISSING


def test_state_equals_passes_on_match() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}
    constraint = StateEquals(path="tickets.T-1.status", expected="closed")

    assert grade_state_constraint(constraint, state) is True


def test_state_equals_fails_on_mismatch() -> None:
    state = {"tickets": {"T-1": {"status": "open"}}}
    constraint = StateEquals(path="tickets.T-1.status", expected="closed")

    assert grade_state_constraint(constraint, state) is False


def test_state_equals_fails_on_missing_path() -> None:
    constraint = StateEquals(path="tickets.T-9.status", expected="closed")

    assert grade_state_constraint(constraint, {"tickets": {}}) is False


def test_state_contains_passes_when_member_present() -> None:
    state = {"docs": {"ids": ["doc-1", "doc-2"]}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is True


def test_state_contains_fails_when_member_absent() -> None:
    state = {"docs": {"ids": ["doc-2"]}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is False


def test_state_contains_fails_on_non_container() -> None:
    state = {"docs": {"ids": 42}}
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, state) is False


def test_state_contains_fails_on_missing_path() -> None:
    constraint = StateContains(path="docs.ids", expected="doc-1")

    assert grade_state_constraint(constraint, {"docs": {}}) is False


def _trajectory(final_state):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def test_grade_final_state_passes_when_all_constraints_hold() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory({"tickets": {"T-1": {"status": "closed"}}}),
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert result.grader_id == "final_state"


def test_grade_final_state_fails_with_none_failure_reason() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory({"tickets": {"T-1": {"status": "open"}}}),
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason is None
    assert "constraints" in result.evidence


def test_grade_final_state_missing_path_fails_without_raising() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-9.status", expected="closed"),)
    )
    result = grade_final_state(
        spec=spec, initial_state=None, trajectory=_trajectory({"tickets": {}})
    )

    assert result.passed is False
