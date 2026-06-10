from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import (
    grade_result_to_dict,
    run_result_to_dict,
    trajectory_from_dict,
    trajectory_to_dict,
    turn_from_dict,
    turn_to_dict,
)
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)

TURNS = (
    MessageTurn(role="user", content="Close ticket T-7."),
    ToolCallTurn(
        tool_calls=(
            ToolCall(
                call_id="c1",
                name="update_ticket",
                arguments={"ticket_id": "T-7", "status": "closed"},
            ),
        ),
        content=None,
    ),
    ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ticket_id": "T-7"})),
    ToolResultTurn(call_id="c2", outcome=ToolFailure(error="unknown ticket_id: T-9")),
    MessageTurn(role="assistant", content="Done."),
)


def test_every_turn_variant_round_trips() -> None:
    for turn in TURNS:
        assert turn_from_dict(turn_to_dict(turn)) == turn


def test_trajectory_round_trips_including_parse_failure() -> None:
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=12, completion_tokens=7, latency_s=0.25),
        run_index=1,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw='{"q": ', error="bad json"),
    )

    assert trajectory_from_dict(trajectory_to_dict(trajectory)) == trajectory


def test_trajectory_from_dict_applies_defaults() -> None:
    trajectory = trajectory_from_dict(
        {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
    )

    assert trajectory.usage == Usage(
        prompt_tokens=0, completion_tokens=0, latency_s=0.0
    )
    assert trajectory.run_index == 0
    assert trajectory.stop_reason == "completed"
    assert trajectory.parse_failure is None


def test_run_result_to_dict_is_json_shaped() -> None:
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=0,
        trajectory=trajectory_from_dict(
            {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=False,
            score=0.0,
            evidence={"error": "x"},
            failure_reason="wrong_tool",
        ),
    )
    data = run_result_to_dict(run)

    assert data["task_id"] == "ws-001"
    assert data["grade"]["failure_reason"] == "wrong_tool"
    assert data["trajectory"]["turns"][0]["type"] == "message"


def test_grade_result_to_dict_keeps_none_failure_reason() -> None:
    grade = GradeResult(grader_id="output_match", passed=True, score=1.0, evidence={})

    assert grade_result_to_dict(grade)["failure_reason"] is None
