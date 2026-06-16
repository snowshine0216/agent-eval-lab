from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(task_id, cond, passed, rounds=3):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
        run_index=0,
        stop_reason="completed_natural",
        rounds=rounds,
    )
    return RunResult(
        task_id=task_id,
        condition_id=cond,
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def _outcome(task_id, cond, passes):
    runs = tuple(_run(task_id, cond, p) for p in passes)
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def _pricing():
    return PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.74, output_per_mtok=3.48
            )
        },
    )


def test_d_only_first_run_renders_d_and_marks_f_b_not_run():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {
        cond: {"D": tuple(_outcome(f"t{i}", cond, [True] * 5) for i in range(3))}
    }
    report = build_m1_report(
        spec=_spec(),
        outcomes_by_condition_domain=outcomes,
        pricing=_pricing(),
        seed=20260613,
        n_resamples=200,
        alpha=0.05,
    )
    d_results = [r for r in report.per_domain_results if r.domain == "D"]
    assert d_results and d_results[0].estimate == 1.0
    # F and B were not run -> no per-domain result for them under this condition
    assert not any(r.domain == "F" for r in report.per_domain_results)
    assert "F" in report.domains_not_run and "B" in report.domains_not_run
    assert "D" not in report.domains_not_run


def test_composite_over_present_domains_only():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {
        cond: {"D": tuple(_outcome(f"t{i}", cond, [True] * 5) for i in range(3))}
    }
    report = build_m1_report(
        spec=_spec(),
        outcomes_by_condition_domain=outcomes,
        pricing=_pricing(),
        seed=20260613,
        n_resamples=200,
        alpha=0.05,
    )
    comp = [r for r in report.composites if r.condition_id == cond][0]
    assert comp.estimate == 1.0  # only D present -> composite == D
    assert comp.void is True  # F/B dropped -> reduced coverage disclosed


def test_spec_hash_and_provenance_carried():
    spec = _spec()
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    report = build_m1_report(
        spec=spec,
        outcomes_by_condition_domain=outcomes,
        pricing=_pricing(),
        seed=20260613,
        n_resamples=100,
        alpha=0.05,
    )
    assert report.spec_hash == spec.spec_hash
    assert report.dataset_snapshot_hash == "ds"
    assert report.classifier_version == "fc-v4"


def test_deterministic_for_same_inputs():
    spec = _spec()
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {
        cond: {"D": tuple(_outcome(f"t{i}", cond, [i % 2 == 0] * 5) for i in range(4))}
    }
    r1 = build_m1_report(
        spec=spec,
        outcomes_by_condition_domain=outcomes,
        pricing=_pricing(),
        seed=7,
        n_resamples=300,
        alpha=0.05,
    )
    r2 = build_m1_report(
        spec=spec,
        outcomes_by_condition_domain=outcomes,
        pricing=_pricing(),
        seed=7,
        n_resamples=300,
        alpha=0.05,
    )
    d1 = [r for r in r1.per_domain_results if r.domain == "D"][0]
    d2 = [r for r in r2.per_domain_results if r.domain == "D"][0]
    assert (d1.estimate, d1.ci_lower, d1.ci_upper) == (
        d2.estimate,
        d2.ci_lower,
        d2.ci_upper,
    )
