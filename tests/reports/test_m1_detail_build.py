from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import (
    CondDomainEfficiency,
    cond_domain_efficiency,
)

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _run(
    task_id, idx, *, rounds, prompt, completion, stop="completed_natural",
    safety_cap_bound=False, max_rounds_bound=False, max_rounds=None, safety_cap=None,
    tool_calls=None, passed=False,
):
    return RunResult(
        task_id=task_id,
        condition_id=_COND,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=prompt, completion_tokens=completion,
                        latency_s=1.0),
            run_index=idx,
            stop_reason=stop,
            rounds=rounds,
            tool_call_counts=tool_calls or {},
            safety_cap_bound=safety_cap_bound,
            max_rounds_bound=max_rounds_bound,
            max_rounds=max_rounds,
            safety_cap=safety_cap,
        ),
        grade=GradeResult(grader_id="g", passed=passed,
                          score=1.0 if passed else 0.0, evidence={}),
    )


def test_empty_runs_is_zero_summary():
    eff = cond_domain_efficiency(runs=(), condition_id=_COND, pricing=_PRICING)
    assert eff == CondDomainEfficiency(
        rounds_median=0.0, rounds_min=0, rounds_max=0, censored_count=0,
        cap_bound=None, prompt_tokens=0, completion_tokens=0, total_tokens=0,
        cost_usd=None, tool_call_totals={}, safety_cap_hits=0, max_rounds_hits=0,
        stop_reason_counts={},
    )


def test_tokens_observed_over_all_runs_including_capped():
    runs = (
        _run("t1", 0, rounds=5, prompt=100, completion=50),
        _run("t1", 1, rounds=40, prompt=200, completion=80, stop="max_rounds",
             max_rounds_bound=True, max_rounds=40),
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
        _run("t1", 0, rounds=3, prompt=1, completion=1,
             tool_calls={"read_file": 2, "str_replace": 1}),
        _run("t1", 1, rounds=3, prompt=1, completion=1, stop="safety_cap",
             safety_cap_bound=True, safety_cap=60,
             tool_calls={"read_file": 1}),
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
