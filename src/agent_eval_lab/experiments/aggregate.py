"""Pure aggregation: ReplacementOutcomes + MetricDef -> ExperimentResult.

The single place that knows the validity/void/INCOMPLETE/censoring rules (D34,
D35, D38, §6, §18.2). Chooses the CI method off MetricDef.ci_method:
cluster_bootstrap (D/B), binomial_exact (F, Clopper-Pearson), none (efficiency).
Never scores a void task; flags the domain void if any task voided. Seeded
bootstrap (RNG argument, no global). Stdlib only.
"""

from __future__ import annotations

import math as _math
from collections.abc import Sequence
from dataclasses import dataclass
from statistics import median

from agent_eval_lab.experiments.schema import DomainWeight, ExperimentResult, MetricDef
from agent_eval_lab.metrics.binomial import clopper_pearson_ci
from agent_eval_lab.metrics.reliability import (
    pass_pow_k,
    pass_pow_k_bootstrap_ci,
    task_reliability,
    token_totals,
)
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.multi_run import ReplacementOutcome


def _complete_runs(outcomes: Sequence[ReplacementOutcome]) -> list[RunResult]:
    """All valid runs from NON-void outcomes (a void task is INCOMPLETE -> dropped)."""
    runs: list[RunResult] = []
    for o in outcomes:
        if o.void:
            continue
        runs.extend(o.valid_runs)
    return runs


def aggregate_domain_metric(
    *,
    outcomes: Sequence[ReplacementOutcome],
    metric: MetricDef,
    condition_id: str,
    experiment_id: str,
    spec_hash: str,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> ExperimentResult:
    any_void = any(o.void for o in outcomes)
    complete = _complete_runs(outcomes)
    invalid_run_count = sum(
        sum(1 for a in o.attempts if not a.valid) for o in outcomes
    )
    if not complete:
        # Every task voided / no scoreable run: never invent a number.
        return ExperimentResult(
            experiment_id=experiment_id, spec_hash=spec_hash,
            condition_id=condition_id, domain=metric.domain,
            metric_name=metric.name, estimate=0.0,
            ci_lower=None, ci_upper=None, ci_method=metric.ci_method,
            valid_run_count=0, invalid_run_count=invalid_run_count, void=True,
        )
    estimate = pass_pow_k(complete)
    ci_lower: float | None = None
    ci_upper: float | None = None
    if metric.ci_method == "cluster_bootstrap":
        ci = pass_pow_k_bootstrap_ci(
            complete, n_resamples=n_resamples, seed=seed, alpha=alpha
        )
        ci_lower, ci_upper = ci.lo, ci.hi
    elif metric.ci_method == "binomial_exact":
        reliable = task_reliability(complete)
        n = len(reliable)
        x = sum(reliable.values())
        bci = clopper_pearson_ci(successes=x, n=n, alpha=alpha)
        ci_lower, ci_upper = bci.lo, bci.hi
    # ci_method == "none": leave both None.
    return ExperimentResult(
        experiment_id=experiment_id, spec_hash=spec_hash,
        condition_id=condition_id, domain=metric.domain, metric_name=metric.name,
        estimate=estimate, ci_lower=ci_lower, ci_upper=ci_upper,
        ci_method=metric.ci_method, valid_run_count=len(complete),
        invalid_run_count=invalid_run_count, void=any_void,
    )


# ---------------------------------------------------------------------------
# Efficiency summary (DEC-6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class EfficiencySummary:
    median_rounds: float
    total_tokens: int
    median_wall_time_s: float
    n_censored: int  # valid runs with safety_cap_bound=True (right-censored, D35)
    n_runs: int


def efficiency_summary(*, outcomes: Sequence[ReplacementOutcome]) -> EfficiencySummary:
    runs = _complete_runs(outcomes)
    if not runs:
        return EfficiencySummary(
            median_rounds=0.0, total_tokens=0, median_wall_time_s=0.0,
            n_censored=0, n_runs=0,
        )
    prompt, completion = token_totals(runs)
    return EfficiencySummary(
        median_rounds=median(r.trajectory.rounds for r in runs),
        total_tokens=prompt + completion,
        median_wall_time_s=median(r.trajectory.wall_time_s for r in runs),
        n_censored=sum(1 for r in runs if r.trajectory.safety_cap_bound),
        n_runs=len(runs),
    )


# ---------------------------------------------------------------------------
# Macro composite (DEC-3)
# ---------------------------------------------------------------------------

COMPOSITE_CI_METHOD = "weighted_halfwidth_propagation"


def macro_composite(
    *,
    per_domain_primary: Sequence[ExperimentResult],
    weights: Sequence[DomainWeight],
    condition_id: str,
    experiment_id: str,
    spec_hash: str,
) -> ExperimentResult:
    """Weighted mean of per-domain PRIMARY estimates (D23/§18.2), weighted by
    DOMAIN (default equal), never a raw task pool. Missing or void domains are
    dropped and the remaining weights renormalized; any drop sets void=True so
    the renderer discloses the reduced coverage. CI = conservative half-width
    propagation under independence (DEC-3); deterministic, no RNG."""
    weight_of = {w.domain: w.weight for w in weights}
    contributing = [
        r for r in per_domain_primary if not r.void and r.estimate is not None
    ]
    dropped = len(per_domain_primary) - len(contributing) or (
        len(weights) > len({r.domain for r in per_domain_primary})
    )
    total_w = sum(weight_of.get(r.domain, 0.0) for r in contributing)
    # void when no domain contributes OR the contributing domains carry no weight
    # (all-zero weights -> no defensible composite; avoids a ZeroDivisionError — L1).
    if not contributing or total_w <= 0.0:
        return ExperimentResult(
            experiment_id=experiment_id, spec_hash=spec_hash,
            condition_id=condition_id, domain="composite", metric_name="composite",
            estimate=0.0, ci_lower=None, ci_upper=None,
            ci_method=COMPOSITE_CI_METHOD, valid_run_count=0, invalid_run_count=0,
            void=True,
        )
    estimate = (
        sum(weight_of.get(r.domain, 0.0) * r.estimate for r in contributing) / total_w
    )
    # Propagate half-widths under independence; missing per-domain CI -> 0 contribution.
    var = 0.0
    for r in contributing:
        w_norm = weight_of.get(r.domain, 0.0) / total_w
        if r.ci_lower is not None and r.ci_upper is not None:
            half = (r.ci_upper - r.ci_lower) / 2.0
            var += (w_norm * half) ** 2
    spread = _math.sqrt(var)
    return ExperimentResult(
        experiment_id=experiment_id, spec_hash=spec_hash, condition_id=condition_id,
        domain="composite", metric_name="composite", estimate=estimate,
        ci_lower=max(0.0, estimate - spread), ci_upper=min(1.0, estimate + spread),
        ci_method=COMPOSITE_CI_METHOD,
        valid_run_count=sum(r.valid_run_count for r in contributing),
        invalid_run_count=sum(r.invalid_run_count for r in contributing),
        void=bool(dropped),
    )
