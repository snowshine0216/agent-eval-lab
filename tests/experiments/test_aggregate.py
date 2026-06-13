from agent_eval_lab.experiments.aggregate import aggregate_domain_metric
from agent_eval_lab.experiments.schema import MetricDef
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(task_id, passed, *, rounds=3, safety_cap=False, cond="m1"):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
        run_index=0,
        stop_reason="safety_cap" if safety_cap else "completed_natural",
        rounds=rounds,
        safety_cap_bound=safety_cap,
    )
    return RunResult(
        task_id=task_id, condition_id=cond, run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="g", passed=passed, score=1.0 if passed else 0.0,
                          evidence={}),
    )


def _outcome(task_id, passes, *, void=False, cond="m1"):
    runs = tuple(_run(task_id, p, cond=cond) for p in passes)
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=void)


PASS_POW_K = MetricDef(
    name="pass_pow_k", domain="D", primary=True, aggregation="pass_pow_k",
    ci_method="cluster_bootstrap", validity_mask=True, censoring_policy="failure",
)
F_PASS_POW_K = MetricDef(
    name="pass_pow_k", domain="F", primary=True, aggregation="pass_pow_k",
    ci_method="binomial_exact", validity_mask=True, censoring_policy="failure",
)


def test_d_domain_uses_cluster_bootstrap_ci():
    # 3 tasks, all reliable -> pass^k = 1.0, cluster_bootstrap CI.
    outcomes = (
        _outcome("t1", [True]*3), _outcome("t2", [True]*3), _outcome("t3", [True]*3)
    )
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 1.0
    assert r.ci_method == "cluster_bootstrap"
    assert r.ci_lower is not None and r.ci_upper is not None
    assert r.valid_run_count == 9
    assert r.invalid_run_count == 0
    assert r.void is False


def test_f_domain_uses_binomial_exact_not_bootstrap():
    # 3 tasks, 2 reliable -> Clopper-Pearson on 2/3 (D38).
    outcomes = (
        _outcome("f1", [True]*5), _outcome("f2", [True]*5), _outcome("f3", [False]*5),
    )
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=F_PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 2 / 3
    assert r.ci_method == "binomial_exact"
    assert 0.09 < r.ci_lower < 0.10
    assert 0.99 < r.ci_upper < 1.0


def test_void_task_is_excluded_and_marks_domain_void():
    # t2 voided (INCOMPLETE): scored over the 2 complete tasks, domain.void True.
    outcomes = (
        _outcome("t1", [True]*3),
        _outcome("t2", [True, False], void=True),  # <k valid -> INCOMPLETE
        _outcome("t3", [False]*3),
    )
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    # complete tasks: t1 reliable, t3 not -> 1/2 = 0.5; t2 NOT scored.
    assert r.estimate == 0.5
    assert r.void is True


def test_safety_cap_run_counts_as_pass_pow_k_failure():
    # A safety-capped run has grade.passed=False -> task not reliable (D35).
    outcomes = (_outcome_with_cap(),)
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.estimate == 0.0


def _outcome_with_cap():
    runs = (
        _run("tc", True), _run("tc", True),
        _run("tc", False, safety_cap=True),  # capped = failed -> task not all-pass
    )
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_all_void_domain_returns_void_result_with_none_estimate():
    outcomes = (_outcome("t1", [True], void=True),)
    r = aggregate_domain_metric(
        outcomes=outcomes, metric=PASS_POW_K, condition_id="m1",
        experiment_id="M1", spec_hash="abc", seed=1, n_resamples=200, alpha=0.05,
    )
    assert r.void is True
    assert r.estimate == 0.0  # no scoreable task -> 0.0 estimate, CI None, void flagged
    assert r.ci_lower is None and r.ci_upper is None


def test_composite_all_zero_weights_is_void_not_crash():
    # review L1: a composite over domains whose weights are all 0 must return a
    # void composite (no defensible mean), never raise ZeroDivisionError.
    from agent_eval_lab.experiments.aggregate import macro_composite
    from agent_eval_lab.experiments.schema import DomainWeight, ExperimentResult

    d = ExperimentResult(
        experiment_id="e", spec_hash="h", condition_id="c", domain="D",
        metric_name="pass_pow_k", estimate=0.8, ci_lower=0.5, ci_upper=1.0,
        ci_method="cluster_bootstrap", valid_run_count=5, invalid_run_count=0,
        void=False,
    )
    comp = macro_composite(
        experiment_id="e", spec_hash="h", condition_id="c",
        per_domain_primary=[d], weights=[DomainWeight(domain="D", weight=0.0)],
    )
    assert comp.void is True
    assert comp.ci_lower is None and comp.ci_upper is None
