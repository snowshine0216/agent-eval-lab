"""Pure M1 per-domain detail report: build + render, no I/O (mirrors m1.py).

Derives per-task / per-condition pass matrices, grader-aware failure gaps
(evidence_summary), edit signals (edit_paths), task-defect candidates (defects),
fc-v4 classification per task×condition (classify), and a rich per-(condition,
domain) efficiency rollup (CondDomainEfficiency). Every derived value is a pure
function of records + spec + pricing; all iteration is over sorted keys, so the
render is deterministic (byte-identical for fixed input). REPORT-LAYER ONLY: no
runner, no scoring, no pass^k math.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from agent_eval_lab.experiments.pricing import PricingSnapshot, condition_cost_usd
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class CondDomainEfficiency:
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int
    cap_bound: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int
    max_rounds_hits: int
    stop_reason_counts: Mapping[str, int]


def _is_censored(run: RunResult) -> bool:
    return run.trajectory.safety_cap_bound or run.trajectory.max_rounds_bound


def _cap_bound_of(run: RunResult) -> int | None:
    t = run.trajectory
    if t.max_rounds_bound:
        return t.max_rounds
    if t.safety_cap_bound:
        return t.safety_cap
    return None


def _counts(values: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in sorted(values):
        out[v] = out.get(v, 0) + 1
    return out


def cond_domain_efficiency(
    *,
    runs: Sequence[RunResult],
    condition_id: str,
    pricing: PricingSnapshot,
) -> CondDomainEfficiency:
    if not runs:
        return CondDomainEfficiency(
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
    rounds = [r.trajectory.rounds for r in runs]
    censored = [r for r in runs if _is_censored(r)]
    cap_bound = _cap_bound_of(censored[0]) if censored else None
    prompt = sum(r.trajectory.usage.prompt_tokens for r in runs)
    completion = sum(r.trajectory.usage.completion_tokens for r in runs)
    tool_totals: dict[str, int] = {}
    for r in runs:
        for tool in sorted(r.trajectory.tool_call_counts):
            tool_totals[tool] = tool_totals.get(tool, 0) + r.trajectory.tool_call_counts[
                tool
            ]
    stop_counts = _counts([r.trajectory.stop_reason for r in runs])
    cost = (
        condition_cost_usd(runs, condition_id, pricing)
        if condition_id in pricing.prices
        else None
    )
    return CondDomainEfficiency(
        rounds_median=median(rounds),
        rounds_min=min(rounds),
        rounds_max=max(rounds),
        censored_count=len(censored),
        cap_bound=cap_bound,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cost_usd=cost,
        tool_call_totals=tool_totals,
        safety_cap_hits=stop_counts.get("safety_cap", 0),
        max_rounds_hits=stop_counts.get("max_rounds", 0),
        stop_reason_counts=stop_counts,
    )
