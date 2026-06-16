"""is_env_invalid_run: provider-side AND oracle-side env-invalidity (D34)."""

from agent_eval_lab.records.grade import GradeResult, RunResult, is_env_invalid_run
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    PROVIDER_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)


def _run(*, parse_failure=None, evidence) -> RunResult:
    stop = "parse_failure" if parse_failure is not None else "completed_natural"
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason=stop,
        parse_failure=parse_failure,
    )
    grade = GradeResult(
        grader_id="node_execution", passed=False, score=0.0, evidence=evidence
    )
    return RunResult(
        task_id="t", condition_id="c", run_index=0, trajectory=traj, grade=grade
    )


# ---- provider-side env-invalidity (existing behavior, must be preserved) ----


def test_provider_error_run_is_env_invalid() -> None:
    run = _run(
        parse_failure=ParseFailure(raw="HTTP 403", error=PROVIDER_ERROR), evidence={}
    )
    assert is_env_invalid_run(run) is True


def test_no_choices_run_is_env_invalid() -> None:
    run = _run(parse_failure=ParseFailure(raw="", error=NO_CHOICES_ERROR), evidence={})
    assert is_env_invalid_run(run) is True


def test_plain_model_fail_is_not_env_invalid() -> None:
    run = _run(evidence={"execution": "run", "status": "failed"})
    assert is_env_invalid_run(run) is False


# ---- oracle-side env-invalidity (the grader-set env_invalid marker) ---------


def test_grade_marked_env_invalid_is_env_invalid() -> None:
    run = _run(evidence={"execution": "run", "status": "error", "env_invalid": True})
    assert is_env_invalid_run(run) is True


def test_nested_allof_env_invalid_sub_result_is_env_invalid() -> None:
    # Real F verifications wrap NodeExecutionSpec(s) in AllOf, so the marker sits
    # under evidence['sub_results'][*]['evidence'] (composite.py nesting).
    evidence = {
        "sub_results": [
            {
                "grader_id": "node_execution",
                "passed": False,
                "failure_reason": None,
                "evidence": {
                    "execution": "run",
                    "status": "error",
                    "env_invalid": True,
                },
            }
        ]
    }
    assert is_env_invalid_run(_run(evidence=evidence)) is True


def test_nested_allof_plain_fail_is_not_env_invalid() -> None:
    evidence = {
        "sub_results": [
            {
                "grader_id": "node_execution",
                "passed": False,
                "failure_reason": None,
                "evidence": {"execution": "run", "status": "failed"},
            }
        ]
    }
    assert is_env_invalid_run(_run(evidence=evidence)) is False
