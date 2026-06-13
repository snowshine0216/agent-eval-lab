from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1 import build_m1_report, render_markdown
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _outcome(tid, cond, passes):
    runs = tuple(
        RunResult(
            task_id=tid, condition_id=cond, run_index=i,
            trajectory=Trajectory(
                turns=(MessageTurn(role="assistant", content="x"),),
                usage=Usage(
                    prompt_tokens=10, completion_tokens=5, latency_s=0.1
                ),
                run_index=i, stop_reason="completed_natural", rounds=3,
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
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_same_runs_and_spec_render_byte_identical():
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    pricing = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.0, output_per_mtok=2.0
            ),
            "minimax:MiniMax-M3": PricePoint(
                input_per_mtok=0.5, output_per_mtok=1.0
            ),
        },
    )
    _ds = "deepseek:deepseek-v4-pro"
    _mm = "minimax:MiniMax-M3"
    outcomes = {
        _ds: {"D": tuple(
            _outcome(f"t{i}", _ds, [i % 2 == 0]*5) for i in range(6)
        )},
        _mm: {"D": tuple(
            _outcome(f"t{i}", _mm, [True]*5) for i in range(6)
        )},
    }
    kw = dict(
        spec=spec, outcomes_by_condition_domain=outcomes, pricing=pricing,
        seed=20260613, n_resamples=1000, alpha=0.05,
    )
    md1 = render_markdown(build_m1_report(**kw))
    md2 = render_markdown(build_m1_report(**kw))
    assert md1 == md2
