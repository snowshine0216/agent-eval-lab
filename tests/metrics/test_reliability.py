import pytest

from agent_eval_lab.metrics.reliability import (
    failure_counts,
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    pass_pow_k_bootstrap_ci,
    task_reliability,
    token_totals,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _run(
    task_id: str,
    run_index: int,
    passed: bool,
    failure_reason: str | None = None,
    safety_cap_bound: bool = False,
) -> RunResult:
    return RunResult(
        task_id=task_id,
        condition_id="local:qwen3-8b",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=0.5),
            run_index=run_index,
            stop_reason="completed",
            safety_cap_bound=safety_cap_bound,
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
    with pytest.raises(ValueError, match="no results"):
        mean_latency_s(())


def test_failure_counts_groups_by_category() -> None:
    results = RESULTS + (_run("c", 0, False, None),)

    assert failure_counts(results) == {"wrong_args": 1, "unclassified": 1}


def test_token_totals_and_latency() -> None:
    assert token_totals(RESULTS) == (400, 80)
    assert mean_latency_s(RESULTS) == 0.5


def _task_runs(task_id: str, k: int, passed: bool):
    return tuple(_run(task_id, i, passed) for i in range(k))


# Fixture: 3 tasks, k=2. a,b reliable (all pass); c unreliable (all fail).
# pass^k point = 2/3. Cluster-by-task resampling 3 task ids.
CLUSTER_RESULTS = (
    *_task_runs("a", 2, True),
    *_task_runs("b", 2, True),
    *_task_runs("c", 2, False),
)


def test_pass_pow_k_bootstrap_ci_is_seeded_and_deterministic() -> None:
    from agent_eval_lab.metrics.reliability import pass_pow_k_bootstrap_ci

    ci1 = pass_pow_k_bootstrap_ci(
        CLUSTER_RESULTS, n_resamples=2000, seed=20260610, alpha=0.05
    )
    ci2 = pass_pow_k_bootstrap_ci(
        CLUSTER_RESULTS, n_resamples=2000, seed=20260610, alpha=0.05
    )
    assert ci1 == ci2
    assert ci1.point == pytest.approx(2 / 3)
    # Verified offline: with the task as the unit a resample can omit a/b entirely.
    assert ci1.lo == pytest.approx(0.0)
    assert ci1.hi == pytest.approx(1.0)
    assert ci1.n_degenerate == 0  # Resolved Q2: no degeneracy class for pass^k


def test_pass_pow_k_bootstrap_cluster_unit_differs_from_naive_run_level() -> None:
    """Discriminating vector (Resolved Q5): the task is the resampling unit.
    3 tasks, k=3, a/b all-pass, c all-fail (deterministic). A naive run-level
    resample of the 9 runs almost never drops a whole task, so its lower bound
    is 0.5; cluster-by-task can omit a/b entirely, giving a lower bound of 0.0."""
    from agent_eval_lab.metrics.reliability import pass_pow_k_bootstrap_ci

    results = (
        *_task_runs("a", 3, True),
        *_task_runs("b", 3, True),
        *_task_runs("c", 3, False),
    )
    ci = pass_pow_k_bootstrap_ci(results, n_resamples=2000, seed=20260610, alpha=0.05)
    assert ci.point == pytest.approx(2 / 3)
    assert ci.lo == pytest.approx(0.0)  # cluster-by-task, NOT the naive 0.5
    assert ci.hi == pytest.approx(1.0)


def test_paired_diff_ci_structural_pairing_and_point() -> None:
    from agent_eval_lab.metrics.reliability import paired_pass_pow_k_diff_ci

    # Identical task universe {t1..t4}. A reliable on t1,t2; B additionally on t3.
    # pass^k(A)=0.5, pass^k(B)=0.75, point diff = +0.25.
    a = (
        *_task_runs("t1", 2, True),
        *_task_runs("t2", 2, True),
        *_task_runs("t3", 2, False),
        *_task_runs("t4", 2, False),
    )
    b = (
        *_task_runs("t1", 2, True),
        *_task_runs("t2", 2, True),
        *_task_runs("t3", 2, True),
        *_task_runs("t4", 2, False),
    )
    ci = paired_pass_pow_k_diff_ci(a, b, n_resamples=2000, seed=20260610, alpha=0.05)
    assert ci.point == pytest.approx(0.25)
    # Verified offline: one task-id multiset applied to BOTH configs -> diff is
    # (count of t3 in the sample)/4, so the 95% interval is [0.0, 0.75].
    assert ci.lo == pytest.approx(0.0)
    assert ci.hi == pytest.approx(0.75)


def test_paired_diff_ci_raises_on_mismatched_task_universe() -> None:
    from agent_eval_lab.metrics.reliability import paired_pass_pow_k_diff_ci

    a = (*_task_runs("t1", 2, True), *_task_runs("t2", 2, True))
    b = (*_task_runs("t1", 2, True), *_task_runs("t3", 2, True))  # t3 != t2
    with pytest.raises(ValueError, match="identical task-id universe"):
        paired_pass_pow_k_diff_ci(a, b, n_resamples=10, seed=1, alpha=0.05)


def test_bootstrap_all_pass_and_all_fail_give_finite_cis_not_degenerate() -> None:
    """Resolved Q2: all-pass and all-fail resamples are legitimate pass^k of
    1.0/0.0, never a degenerate flag."""
    from agent_eval_lab.metrics.reliability import pass_pow_k_bootstrap_ci

    all_pass = (*_task_runs("a", 2, True), *_task_runs("b", 2, True))
    all_fail = (*_task_runs("a", 2, False), *_task_runs("b", 2, False))
    cp = pass_pow_k_bootstrap_ci(all_pass, n_resamples=500, seed=1, alpha=0.05)
    cf = pass_pow_k_bootstrap_ci(all_fail, n_resamples=500, seed=1, alpha=0.05)
    assert cp.point == 1.0 and cp.lo == 1.0 and cp.hi == 1.0 and cp.n_degenerate == 0
    assert cf.point == 0.0 and cf.lo == 0.0 and cf.hi == 0.0 and cf.n_degenerate == 0


def test_tier_of_maps_id_ranges() -> None:
    from agent_eval_lab.metrics.reliability import tier_of

    tiers = {"ws2-001": "T1", "ws2-006": "T2", "ws2-018": "T3", "ws2-040": "T4"}
    assert tier_of("ws2-001", tiers) == "T1"
    assert tier_of("ws2-040", tiers) == "T4"


def test_pass_pow_k_by_tier_filters_results() -> None:
    from agent_eval_lab.metrics.reliability import pass_pow_k_by_tier

    results = (
        *_task_runs("ws2-001", 2, True),  # T1, reliable
        *_task_runs("ws2-018", 2, False),  # T3, unreliable
        *_task_runs("ws2-019", 2, True),  # T3, reliable
    )
    tiers = {"ws2-001": "T1", "ws2-018": "T3", "ws2-019": "T3"}
    by_tier = pass_pow_k_by_tier(results, tiers)
    assert by_tier["T1"] == pytest.approx(1.0)
    assert by_tier["T3"] == pytest.approx(0.5)
    assert "T2" not in by_tier  # tiers with no results are omitted


def test_pass_pow_k_censors_a_capped_pass() -> None:
    # Task X: both runs grade-passed, but one is safety_cap_bound → NOT reliable.
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    assert pass_pow_k(results) == 0.0


def test_task_reliability_censors_a_capped_pass() -> None:
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    assert task_reliability(results) == {"x": False}


def test_pass_pow_k_uncapped_all_pass_is_reliable() -> None:
    results = (_run("x", 0, True), _run("x", 1, True))
    assert pass_pow_k(results) == 1.0


def test_bootstrap_ci_inherits_the_censor() -> None:
    # A capped pass drags the point estimate to 0.0 through task_reliability.
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    ci = pass_pow_k_bootstrap_ci(results, n_resamples=200, seed=1, alpha=0.05)
    assert ci.point == 0.0


def test_max_rounds_bound_field_now_present_on_trajectory() -> None:
    # item 002: max_rounds_bound is now a real Trajectory field (default False).
    # This replaces the former "field absent" test — the field is always present.
    results = (_run("x", 0, True), _run("x", 1, True))
    assert hasattr(results[0].trajectory, "max_rounds_bound")
    assert results[0].trajectory.max_rounds_bound is False
    assert pass_pow_k(results) == 1.0


def _run_with_max_rounds(*, passed: bool, max_rounds_bound: bool) -> RunResult:
    from agent_eval_lab.records.turns import MessageTurn

    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="max_rounds" if max_rounds_bound else "completed_natural",
        rounds=20,
        max_rounds_bound=max_rounds_bound,
    )
    return RunResult(
        task_id="t",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g",
            passed=passed,
            score=1.0,
            evidence={},
        ),
    )


def test_graded_pass_but_max_rounds_capped_is_censored() -> None:
    # A graded-correct-but-capped run is NOT a reliable pass^k pass (§D.1).
    results = [_run_with_max_rounds(passed=True, max_rounds_bound=True)]
    assert pass_pow_k(results) == 0.0


def test_graded_pass_uncapped_passes() -> None:
    results = [_run_with_max_rounds(passed=True, max_rounds_bound=False)]
    assert pass_pow_k(results) == 1.0


def test_comparisons_fisher_path_inherits_censor() -> None:
    # comparisons.run_planned_comparisons computes the F (Fisher) success count
    # from task_reliability — a capped pass must drop the success count to 0.
    from agent_eval_lab.metrics.reliability import task_reliability as tr

    capped = (_run("x", 0, True), _run("x", 1, True, safety_cap_bound=True))
    assert sum(tr(capped).values()) == 0
