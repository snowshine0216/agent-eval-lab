from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.runners.runner import RunLimits, run_task
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, initial_state


def _task():
    return Task(
        id="t1",
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="search install"),),
            available_tools=({"name": "search_docs"},),
        ),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(
                ExpectedToolCall(name="search_docs", arguments={"query": "install"}),
            )
        ),
        metadata=TaskMetadata(
            split="dev",
            version="1",
            provenance="handwritten",
            world_template_id="workspace",
            difficulty_knob="baseline",
        ),
        initial_state=initial_state(),
    )


def _model():
    return FakeModel(
        scripts={
            "t1": [
                {
                    "type": "tool_call",
                    "name": "search_docs",
                    "arguments": {"query": "install"},
                },
                {"type": "message", "content": "Found it."},
            ]
        }
    )


def test_run_task_emits_k_trajectories():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=3, limits=RunLimits())
    assert [r.run_index for r in results] == [0, 1, 2]
    assert all(r.task_id == "t1" for r in results)


def test_trajectory_carries_cost_latency_and_termination():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    traj = results[0].trajectory
    assert traj.cost_usd >= 0.0
    assert traj.latency_ms >= 0
    assert traj.termination_reason == "stop"
    assert traj.usage["total_tokens"] > 0


def test_tool_result_turn_threaded_into_trajectory():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    kinds = [type(t).__name__ for t in results[0].trajectory.turns]
    assert "ToolCallTurn" in kinds
    assert "ToolResultTurn" in kinds


def test_grade_is_attached_and_passes():
    results = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())
    assert results[0].grade.passed is True


def test_max_tool_calls_limit_terminates_with_reason():
    model = FakeModel(
        scripts={
            "t1": [
                {
                    "type": "tool_call",
                    "name": "search_docs",
                    "arguments": {"query": "a"},
                },
                {
                    "type": "tool_call",
                    "name": "search_docs",
                    "arguments": {"query": "b"},
                },
                {"type": "message", "content": "done"},
            ]
        }
    )
    results = run_task(
        _task(), model, TOOL_SCHEMAS, k=1, limits=RunLimits(max_tool_calls=1)
    )
    assert results[0].trajectory.termination_reason == "max_tool_calls"
    assert results[0].grade.failure_reason == "step_limit_exceeded"


def test_max_turns_limit_terminates_with_reason():
    # Each tool-call step appends 2 turns (call + result); max_turns=2 trips at step 1.
    model = FakeModel(
        scripts={
            "t1": [
                {
                    "type": "tool_call",
                    "name": "search_docs",
                    "arguments": {"query": "a"},
                },
                {
                    "type": "tool_call",
                    "name": "search_docs",
                    "arguments": {"query": "b"},
                },
                {"type": "message", "content": "done"},
            ]
        }
    )
    results = run_task(
        _task(),
        model,
        TOOL_SCHEMAS,
        k=1,
        limits=RunLimits(max_turns=2, max_tool_calls=8),
    )
    assert results[0].trajectory.termination_reason == "max_turns"
