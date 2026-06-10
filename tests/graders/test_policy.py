from agent_eval_lab.graders.policy import grade_trajectory_spec
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import MaxToolCalls, NoToolCall, TrajectorySpec


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
