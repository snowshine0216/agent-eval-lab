from agent_eval_lab.graders.policy import (
    _changed_leaf_paths,
    _is_covered,
    _leaf_paths,
    grade_trajectory_spec,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import (
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    TrajectorySpec,
)


def _trajectory(*turns, final_state=None):
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def _call(name, **arguments):
    return ToolCall(call_id="c", name=name, arguments=arguments)


def test_no_tool_call_passes_when_absent() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="delete_ticket"),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("update_ticket", ticket_id="T-1"),))
    )

    result = grade_trajectory_spec(spec=spec, initial_state=None, trajectory=trajectory)

    assert result.passed is True
    assert result.failure_reason is None


def test_no_tool_call_fails_with_forbidden_action() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="delete_ticket"),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("delete_ticket", ticket_id="T-1"),))
    )

    result = grade_trajectory_spec(spec=spec, initial_state=None, trajectory=trajectory)

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_max_tool_calls_passes_at_limit() -> None:
    spec = TrajectorySpec(constraints=(MaxToolCalls(n=2),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("a"), _call("b"))),
    )

    result = grade_trajectory_spec(spec=spec, initial_state=None, trajectory=trajectory)

    assert result.passed is True


def test_max_tool_calls_fails_with_step_limit_exceeded() -> None:
    spec = TrajectorySpec(constraints=(MaxToolCalls(n=2),))
    trajectory = _trajectory(
        ToolCallTurn(tool_calls=(_call("a"), _call("b"))),
        MessageTurn(role="assistant", content="thinking"),
        ToolCallTurn(tool_calls=(_call("c"),)),
    )

    result = grade_trajectory_spec(spec=spec, initial_state=None, trajectory=trajectory)

    assert result.passed is False
    assert result.failure_reason == "step_limit_exceeded"


def test_changed_leaf_paths_detects_value_change() -> None:
    before = {"tickets": {"T-1": {"status": "open"}}}
    after = {"tickets": {"T-1": {"status": "closed"}}}

    assert _changed_leaf_paths(before, after) == {"tickets.T-1.status"}


def test_changed_leaf_paths_detects_added_and_removed() -> None:
    before = {"a": 1, "b": 2}
    after = {"a": 1, "c": 3}

    assert _changed_leaf_paths(before, after) == {"b", "c"}


def test_is_covered_is_dot_segment_aware() -> None:
    assert _is_covered("tickets.T-1.status", ("tickets.T-1",)) is True
    assert _is_covered("tickets.T-1", ("tickets.T-1",)) is True
    assert _is_covered("tickets.T-10.status", ("tickets.T-1",)) is False


def test_only_modifies_passes_when_change_is_covered() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(final_state={"tickets": {"T-1": {"status": "closed"}}})
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={"tickets": {"T-1": {"status": "open"}}},
        trajectory=trajectory,
    )

    assert result.passed is True


def test_only_modifies_fails_forbidden_action_when_change_outside() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(
        final_state={
            "tickets": {
                "T-1": {"status": "closed"},
                "T-2": {"status": "closed"},
            }
        }
    )
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={
            "tickets": {
                "T-1": {"status": "open"},
                "T-2": {"status": "open"},
            }
        },
        trajectory=trajectory,
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_only_modifies_sibling_prefix_not_covered() -> None:
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(final_state={"tickets": {"T-10": {"status": "closed"}}})
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={"tickets": {"T-10": {"status": "open"}}},
        trajectory=trajectory,
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


# --- Amendment (2026-06-10): empty-mapping leaf semantics ---


def test_leaf_paths_empty_mapping_at_root_yields_no_leaves() -> None:
    """Root empty mapping contributes no leaves (not a phantom key)."""
    assert _leaf_paths({}) == {}


def test_leaf_paths_empty_mapping_nested_yields_no_leaves() -> None:
    """Nested empty mapping also contributes no leaves (root/nested consistency)."""
    assert _leaf_paths({"tickets": {}}) == {}


def test_changed_leaf_paths_empty_to_populated_detects_only_new_leaves() -> None:
    """Empty-to-populated subtree: only real leaf paths detected, no phantom keys."""
    before = {"tickets": {}}
    after = {"tickets": {"T-1": {"status": "closed"}}}

    changed = _changed_leaf_paths(before, after)

    assert changed == {"tickets.T-1.status"}


def test_only_modifies_phantom_path_repro() -> None:
    """Repro 001-ship-blocked: empty initial subtree must not produce phantom-fail."""
    spec = TrajectorySpec(constraints=(OnlyModifies(paths=("tickets.T-1",)),))
    trajectory = _trajectory(final_state={"tickets": {"T-1": {"status": "closed"}}})
    result = grade_trajectory_spec(
        spec=spec,
        initial_state={"tickets": {}},
        trajectory=trajectory,
    )

    assert result.passed is True
    assert result.failure_reason is None


def test_leaf_to_empty_mapping_still_detected_as_change() -> None:
    """Replacing a leaf value with an empty mapping is still detected as a change."""
    before = {"a": 1}
    after = {"a": {}}

    changed = _changed_leaf_paths(before, after)

    # "a" was a leaf in before (value 1); in after it's an empty mapping (no leaves).
    # The union of key sets includes "a" from before, absent from after → changed.
    assert "a" in changed
