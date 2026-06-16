from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import (
    CondDomainEfficiency,
    M1Detail,
    build_m1_detail,
    cond_domain_efficiency,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _run(
    task_id,
    idx,
    *,
    rounds,
    prompt,
    completion,
    stop="completed_natural",
    safety_cap_bound=False,
    max_rounds_bound=False,
    max_rounds=None,
    safety_cap=None,
    tool_calls=None,
    passed=False,
):
    return RunResult(
        task_id=task_id,
        condition_id=_COND,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(
                prompt_tokens=prompt, completion_tokens=completion, latency_s=1.0
            ),
            run_index=idx,
            stop_reason=stop,
            rounds=rounds,
            tool_call_counts=tool_calls or {},
            safety_cap_bound=safety_cap_bound,
            max_rounds_bound=max_rounds_bound,
            max_rounds=max_rounds,
            safety_cap=safety_cap,
        ),
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def test_empty_runs_is_zero_summary():
    eff = cond_domain_efficiency(runs=(), condition_id=_COND, pricing=_PRICING)
    assert eff == CondDomainEfficiency(
        rounds_median=0.0,
        rounds_min=0,
        rounds_max=0,
        censored_count=0,
        cap_bound=None,
        prompt_tokens=0,
        completion_tokens=0,
        total_tokens=0,
        cost_usd=None,
        tool_call_totals={},
        safety_cap_hits=0,
        max_rounds_hits=0,
        stop_reason_counts={},
    )


def test_tokens_observed_over_all_runs_including_capped():
    runs = (
        _run("t1", 0, rounds=5, prompt=100, completion=50),
        _run(
            "t1",
            1,
            rounds=40,
            prompt=200,
            completion=80,
            stop="max_rounds",
            max_rounds_bound=True,
            max_rounds=40,
        ),
    )
    eff = cond_domain_efficiency(runs=runs, condition_id=_COND, pricing=_PRICING)
    assert eff.prompt_tokens == 300
    assert eff.completion_tokens == 130
    assert eff.total_tokens == 430
    assert eff.censored_count == 1
    assert eff.cap_bound == 40
    assert eff.max_rounds_hits == 1
    assert eff.rounds_min == 5 and eff.rounds_max == 40
    # cost = (300*1.0 + 130*2.0) / 1e6
    assert eff.cost_usd == (300 * 1.0 + 130 * 2.0) / 1_000_000


def test_tool_call_totals_and_stop_reason_counts_merge():
    runs = (
        _run(
            "t1",
            0,
            rounds=3,
            prompt=1,
            completion=1,
            tool_calls={"read_file": 2, "str_replace": 1},
        ),
        _run(
            "t1",
            1,
            rounds=3,
            prompt=1,
            completion=1,
            stop="safety_cap",
            safety_cap_bound=True,
            safety_cap=60,
            tool_calls={"read_file": 1},
        ),
    )
    eff = cond_domain_efficiency(runs=runs, condition_id=_COND, pricing=_PRICING)
    assert eff.tool_call_totals == {"read_file": 3, "str_replace": 1}
    assert eff.stop_reason_counts == {"completed_natural": 1, "safety_cap": 1}
    assert eff.safety_cap_hits == 1
    assert eff.cap_bound == 60


def test_cost_none_when_condition_not_priced():
    runs = (_run("t1", 0, rounds=1, prompt=1, completion=1),)
    eff = cond_domain_efficiency(
        runs=runs, condition_id="unpriced:model", pricing=_PRICING
    )
    assert eff.cost_usd is None


# ---------------------------------------------------------------------------
# Task 5: build_m1_detail tests
# ---------------------------------------------------------------------------


def _node_grade(passed, tests, displaced=()):
    return GradeResult(
        grader_id="node_execution",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "execution": "run",
            "status": "passed" if passed else "failed",
            "tests": tests,
            "displaced_paths": list(displaced),
        },
    )


def _f_run(task_id, cond, idx, passed, tests, target_paths=("wdio.conf.ts",)):
    return RunResult(
        task_id=task_id,
        condition_id=cond,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=idx,
            stop_reason="completed_natural",
            rounds=4,
            final_state={"files": {}, "target_paths": list(target_paths)},
        ),
        grade=_node_grade(passed, tests),
    )


def _outcome(runs, *, invalid=0, void=False):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    ) + tuple(
        TrialAttempt(attempt_index=len(runs) + j, valid=False, run=runs[0])
        for j in range(invalid)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=void)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def test_build_detail_per_task_pass_contribution():
    cond = _COND
    runs = [
        _f_run(
            "f1",
            cond,
            i,
            passed=(i == 0),
            tests=[["a", "passed" if i == 0 else "failed"]],
        )
        for i in range(3)
    ]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond: (_outcome(runs),)},
        pricing=_PRICING,
        spec=_spec(),
    )
    assert isinstance(detail, M1Detail)
    cell = detail.tasks[0].cells[0]
    assert cell.valid_trials == 3
    assert cell.passed_trials == 1
    assert cell.per_trial == (True, False, False)


def test_shared_failing_unit_intersection():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [
        _f_run("f1", cond_a, i, passed=False, tests=[["a", "failed"], ["b", "passed"]])
        for i in range(2)
    ]
    runs_b = [
        _f_run("f1", cond_b, i, passed=False, tests=[["a", "failed"], ["b", "failed"]])
        for i in range(2)
    ]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={
            cond_a: (_outcome(runs_a),),
            cond_b: (_outcome(runs_b),),
        },
        pricing=_PRICING,
        spec=_spec(),
    )
    # both conditions fail "a" -> shared; only b fails "b" -> not shared.
    assert detail.tasks[0].shared_failing_units == ("a",)
    assert detail.tasks[0].divergent is False


def test_divergent_when_no_shared_unit():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f1", cond_b, 0, passed=False, tests=[["b", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={
            cond_a: (_outcome(runs_a),),
            cond_b: (_outcome(runs_b),),
        },
        pricing=_PRICING,
        spec=_spec(),
    )
    assert detail.tasks[0].shared_failing_units == ()
    assert detail.tasks[0].divergent is True


def test_invalid_trials_counted_from_attempts():
    cond = _COND
    runs = [_f_run("f1", cond, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond: (_outcome(runs, invalid=2),)},
        pricing=_PRICING,
        spec=_spec(),
    )
    assert detail.tasks[0].cells[0].invalid_trials == 2


def test_condition_missing_task_is_absent_cell():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f2", cond_b, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={
            cond_a: (_outcome(runs_a),),
            cond_b: (_outcome(runs_b),),
        },
        pricing=_PRICING,
        spec=_spec(),
    )
    f1 = next(t for t in detail.tasks if t.task_id == "f1")
    cell_b = next(c for c in f1.cells if c.condition_id == cond_b)
    assert cell_b.present is False


def test_defect_candidate_flagged_when_all_conditions_fail():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f1", cond_b, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={
            cond_a: (_outcome(runs_a),),
            cond_b: (_outcome(runs_b),),
        },
        pricing=_PRICING,
        spec=_spec(),
    )
    assert [c.task_id for c in detail.defect_candidates] == ["f1"]
