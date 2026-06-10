import pytest

from agent_eval_lab.metrics.reliability import (
    failure_counts,
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    token_totals,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _run(task_id: str, run_index: int, passed: bool, failure_reason=None) -> RunResult:
    return RunResult(
        task_id=task_id,
        condition_id="local:qwen3-8b",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=0.5),
            run_index=run_index,
            stop_reason="completed",
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


# Task A passes all runs; task B fails run 1 of 2.
RESULTS = (
    _run("a", 0, True),
    _run("a", 1, True),
    _run("b", 0, True),
    _run("b", 1, False, "wrong_args"),
)


def test_pass_at_1_is_trial_accuracy() -> None:
    assert pass_at_1(RESULTS) == 0.75


def test_pass_pow_k_is_task_level_reliability() -> None:
    assert pass_pow_k(RESULTS) == 0.5


def test_metrics_reject_empty_results() -> None:
    with pytest.raises(ValueError, match="no results"):
        pass_at_1(())
    with pytest.raises(ValueError, match="no results"):
        pass_pow_k(())


def test_failure_counts_groups_by_category() -> None:
    results = RESULTS + (_run("c", 0, False, None),)

    assert failure_counts(results) == {"wrong_args": 1, "unclassified": 1}


def test_token_totals_and_latency() -> None:
    assert token_totals(RESULTS) == (400, 80)
    assert mean_latency_s(RESULTS) == 0.5
