from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report, render_markdown
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _outcome(task_id, cond, passes, void=False):
    runs = tuple(
        RunResult(
            task_id=task_id,
            condition_id=cond,
            run_index=i,
            trajectory=Trajectory(
                turns=(MessageTurn(role="assistant", content="x"),),
                usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
                run_index=i,
                stop_reason="completed_natural",
                rounds=3,
            ),
            grade=GradeResult(
                grader_id="g", passed=p, score=1.0 if p else 0.0, evidence={}
            ),
        )
        for i, p in enumerate(passes)
    )
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=void)


def _report(outcomes):
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    pricing = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.0, output_per_mtok=2.0
            )
        },
    )
    return spec, render_markdown(
        build_m1_report(
            spec=spec,
            outcomes_by_condition_domain=outcomes,
            pricing=pricing,
            seed=20260613,
            n_resamples=200,
            alpha=0.05,
        )
    )


def test_render_includes_spec_hash_and_per_domain_and_composite():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {
        cond: {"D": tuple(_outcome(f"t{i}", cond, [True] * 5) for i in range(3))}
    }
    spec, md = _report(outcomes)
    assert spec.spec_hash in md
    assert "Per-domain scores" in md
    assert "Macro composite" in md
    assert "Pareto" in md
    assert "Failure classification (fc-v4) per condition" in md
    assert "Failure taxonomy" not in md


def test_render_marks_f_and_b_not_yet_run():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "not yet run" in md.lower()
    assert "| F |" in md or "F (not yet run)" in md or "| (all conditions) | F |" in md


def test_render_has_efficiency_and_cost_rollup():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "Efficiency & cost" in md
    # rollup columns
    assert "rounds" in md.lower() and "cost" in md.lower()


def test_render_has_subreport_links_and_headline():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "Subreports" in md
    assert "M1-D-report.md" in md
    # deterministic per-domain headline
    assert "best pass^k" in md


def test_render_flags_void_domain():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {
        cond: {
            "D": (
                _outcome("t0", cond, [True] * 5),
                _outcome("t1", cond, [True, False], void=True),
            )
        }
    }
    _, md = _report(outcomes)
    assert "VOID" in md or "INCOMPLETE" in md


def _mixed_admin_outcome(task_id, cond):
    """One real run (rounds=10) plus one administrative not-executed run (rounds=0).
    The admin run must NOT drag the overview efficiency rollup's rounds median/min."""

    def _run(idx, *, admin):
        return RunResult(
            task_id=task_id,
            condition_id=cond,
            run_index=idx,
            trajectory=Trajectory(
                turns=(MessageTurn(role="assistant", content="x"),),
                usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
                run_index=idx,
                stop_reason="completed_natural",
                rounds=0 if admin else 10,
            ),
            grade=GradeResult(
                grader_id="g",
                passed=False,
                score=0.0,
                evidence=({"marked_failed_not_executed": True} if admin else {}),
            ),
        )

    runs = (_run(0, admin=False), _run(1, admin=True))
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_overview_efficiency_rollup_excludes_administrative_runs():
    # Regression: the overview rollup must agree with the subreport — an admin
    # 0-round trial is excluded, so rounds_min reflects the real run (10), not 0.
    cond = "deepseek:deepseek-v4-pro"
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    pricing = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            cond: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0),
        },
    )
    report = build_m1_report(
        spec=spec,
        outcomes_by_condition_domain={cond: {"F": (_mixed_admin_outcome("t0", cond),)}},
        pricing=pricing,
        seed=20260613,
        n_resamples=200,
        alpha=0.05,
    )
    eff = next(
        e
        for (c, d, e) in report.cond_domain_efficiency_rollup
        if c == cond and d == "F"
    )
    assert eff.rounds_min == 10  # admin 0-round run excluded
    assert eff.rounds_median == 10
    assert "completed_natural" in eff.stop_reason_counts
    assert sum(eff.stop_reason_counts.values()) == 1  # only the real run counted
