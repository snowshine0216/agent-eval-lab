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
    assert "fc-v4" in md or "Failure taxonomy" in md


def test_render_marks_f_and_b_not_yet_run():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "not yet run" in md.lower()
    assert "| F |" in md or "F (not yet run)" in md or "| (all conditions) | F |" in md


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
