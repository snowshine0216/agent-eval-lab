from agent_eval_lab.tasks.codec import from_dict, to_dict
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


def _roundtrip(record):
    return from_dict(type(record), to_dict(record))


def test_tool_call_roundtrip():
    rec = ToolCall(call_id="c1", name="create_ticket", arguments={"title": "x"})
    assert _roundtrip(rec) == rec


def test_message_turn_roundtrip():
    rec = MessageTurn(role="user", content="hi")
    out = to_dict(rec)
    assert out["type"] == "message"
    assert from_dict(MessageTurn, out) == rec


def test_tool_call_turn_roundtrip():
    rec = ToolCallTurn(tool_calls=(ToolCall(call_id="c1", name="t", arguments={}),))
    assert _roundtrip(rec) == rec


def test_tool_result_turn_success_roundtrip():
    rec = ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": 1}))
    out = to_dict(rec)
    assert out["outcome"]["type"] == "success"
    assert from_dict(ToolResultTurn, out) == rec


def test_tool_result_turn_failure_roundtrip():
    rec = ToolResultTurn(call_id="c1", outcome=ToolFailure(error="bad"))
    out = to_dict(rec)
    assert out["outcome"]["type"] == "failure"
    assert from_dict(ToolResultTurn, out) == rec


def test_output_match_spec_roundtrip():
    rec = OutputMatchSpec(expected_output="42")
    assert _roundtrip(rec) == rec


def test_tool_call_match_spec_roundtrip():
    rec = ToolCallMatchSpec(
        expected_tool_calls=(ExpectedToolCall(name="t", arguments={"a": 1}),),
        match="multiset",
    )
    assert _roundtrip(rec) == rec


def test_task_roundtrip_with_tool_call_verification():
    rec = Task(
        id="t1",
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="hi"),),
            available_tools=({"name": "search_docs"},),
        ),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "x"}),),
        ),
        metadata=TaskMetadata(
            split="dev",
            version="1",
            provenance="handwritten",
            world_template_id="workspace",
            difficulty_knob="baseline",
        ),
        initial_state={"tickets": {}, "docs": {}},
    )
    assert _roundtrip(rec) == rec


def test_run_result_roundtrip():
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="done"),),
        usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        cost_usd=0.0001,
        latency_ms=42,
        run_index=0,
        termination_reason="stop",
    )
    grade = GradeResult(grader_id="ast_tool_match", passed=True, score=1.0)
    rec = RunResult(task_id="t1", condition_id="c", run_index=0, trajectory=traj, grade=grade)
    assert _roundtrip(rec) == rec
