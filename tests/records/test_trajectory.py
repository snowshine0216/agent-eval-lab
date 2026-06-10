from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _trajectory(**overrides):
    defaults = dict(
        turns=(MessageTurn(role="user", content="hi"),),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.5),
        run_index=0,
        stop_reason="completed",
    )
    return Trajectory(**{**defaults, **overrides})


def test_trajectory_defaults_to_no_parse_failure() -> None:
    trajectory = _trajectory()

    assert trajectory.parse_failure is None
    assert trajectory.stop_reason == "completed"


def test_trajectory_records_parse_failure() -> None:
    failure = ParseFailure(raw='{"query": ', error="arguments not valid JSON")
    trajectory = _trajectory(stop_reason="parse_failure", parse_failure=failure)

    assert trajectory.parse_failure.error == "arguments not valid JSON"


def test_trajectory_defaults_to_no_final_state() -> None:
    trajectory = _trajectory()

    assert trajectory.final_state is None


def test_trajectory_records_final_state() -> None:
    trajectory = _trajectory(final_state={"tickets": {"T-1": {"status": "closed"}}})

    assert trajectory.final_state == {"tickets": {"T-1": {"status": "closed"}}}


def test_run_result_links_task_condition_and_grade() -> None:
    grade = GradeResult(
        grader_id="ast_tool_match",
        passed=True,
        score=1.0,
        evidence={},
        failure_reason=None,
    )
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=2,
        trajectory=_trajectory(run_index=2),
        grade=grade,
    )

    assert run.run_index == 2
    assert run.grade.passed is True
