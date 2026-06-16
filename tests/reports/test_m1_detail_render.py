from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _node_grade(passed, tests, **extra):
    ev = {"execution": "run", "status": "passed" if passed else "failed",
          "tests": tests, "displaced_paths": []}
    ev.update(extra)
    return GradeResult(grader_id="node_execution", passed=passed,
                       score=1.0 if passed else 0.0, evidence=ev)


def _f_run(idx, passed, tests, *, stop="completed_natural",
           safety_cap_bound=False, max_rounds_bound=False, max_rounds=None, rounds=4):
    return RunResult(
        task_id="f1", condition_id=_COND, run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=idx, stop_reason=stop, rounds=rounds,
            safety_cap_bound=safety_cap_bound, max_rounds_bound=max_rounds_bound,
            max_rounds=max_rounds,
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=_node_grade(passed, tests),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=False)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def _render(runs):
    detail = build_m1_detail(
        domain="F", outcomes_by_condition={_COND: (_outcome(runs),)},
        pricing=_PRICING, spec=_spec(),
    )
    return render_detail(detail)


def test_render_has_all_sections():
    md = _render([_f_run(i, passed=False, tests=[["a", "failed"]]) for i in range(3)])
    assert "# M1 subreport — F" in md
    assert "## Task quick-reference" in md
    assert "## Cross-model summary" in md
    assert "## Per-task detail" in md
    assert "## Task-defect candidates" in md
    assert "## Per-condition efficiency" in md
    assert "## Failure classification (fc-v4) per task × condition" in md


def test_render_per_trial_string_and_gap():
    md = _render([
        _f_run(0, passed=True, tests=[["a", "passed"], ["b", "passed"]]),
        _f_run(1, passed=False, tests=[["a", "passed"], ["b", "failed"]]),
    ])
    assert "✅" in md and "❌" in md
    # grader-aware gap names the failing oracle test
    assert "b" in md


def test_render_censoring_annotation():
    md = _render([
        _f_run(0, passed=False, tests=[["a", "failed"]]),
        _f_run(1, passed=False, tests=[["a", "failed"]],
               stop="max_rounds", max_rounds=40, max_rounds_bound=True, rounds=40),
    ])
    # the censored run must annotate the rounds cell, never silently
    assert "right-censored" in md
    assert "cap 40" in md


def test_render_administrative_label():
    admin = RunResult(
        task_id="f1", condition_id=_COND, run_index=0,
        trajectory=Trajectory(
            turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0, stop_reason="completed_natural", rounds=0,
            final_state={"files": {}, "target_paths": []},
        ),
        grade=GradeResult(grader_id="node_execution", passed=False, score=0.0,
                          evidence={"marked_failed_not_executed": True}),
    )
    md = _render([admin])
    assert "administrative" in md
    assert "not executed" in md
