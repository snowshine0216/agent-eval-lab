from agent_eval_lab.graders.composite import grade_all_of
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.tasks.schema import AllOf, OutputMatchSpec


def _trajectory():
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


def _grader_returning(results):
    """Build a fake grade_trajectory that returns scripted results in order."""
    calls = iter(results)

    def grade(*, verification, trajectory, registry, initial_state):
        return next(calls)

    return grade


def _result(passed, failure_reason=None, grader_id="x"):
    return GradeResult(
        grader_id=grader_id,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={},
        failure_reason=failure_reason,
    )


def test_all_of_passes_when_every_sub_result_passes() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="a"),
            OutputMatchSpec(expected_output="b"),
        )
    )
    grade = _grader_returning([_result(True), _result(True)])

    result = grade_all_of(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory(),
        registry={},
        grade=grade,
    )

    assert result.passed is True
    assert result.score == 1.0
    assert result.failure_reason is None
    assert len(result.evidence["sub_results"]) == 2


def test_all_of_reports_first_failure_reason_and_lists_all_sub_results() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="a"),
            OutputMatchSpec(expected_output="b"),
            OutputMatchSpec(expected_output="c"),
        )
    )
    grade = _grader_returning(
        [
            _result(True),
            _result(False, failure_reason="forbidden_action"),
            _result(False, failure_reason="step_limit_exceeded"),
        ]
    )

    result = grade_all_of(
        spec=spec,
        initial_state=None,
        trajectory=_trajectory(),
        registry={},
        grade=grade,
    )

    assert result.passed is False
    assert result.score == 0.0
    assert result.failure_reason == "forbidden_action"
    assert len(result.evidence["sub_results"]) == 3
