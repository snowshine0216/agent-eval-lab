"""Wire PlannedComparisons to per-comparison p-values + Holm per family (DEC-2).

D/B comparisons use the bootstrap two-sided Delta pass^k p (and the paired
cluster-bootstrap CI); F comparisons use Fisher exact (no bootstrap). Holm is
applied WITHIN each family. Missing arms (partial coverage) are reported as
skipped, never crashed. Seeded; stdlib only.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.experiments.schema import MultiplicityFamily, PlannedComparison
from agent_eval_lab.metrics.binomial import fisher_exact_two_sided
from agent_eval_lab.metrics.multiplicity import (
    HolmDecision,
    PValue,
    bootstrap_diff_p_value,
    holm_step_down,
)
from agent_eval_lab.metrics.reliability import (
    paired_pass_pow_k_diff_ci,
    task_reliability,
)
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class ComparisonRow:
    comparison_name: str
    family_id: str
    domain: str
    skipped: bool
    delta_point: float | None
    ci_lower: float | None
    ci_upper: float | None
    decision: HolmDecision | None


def _arm(runs_by, condition_id, domain) -> list[RunResult]:
    return list(runs_by.get(condition_id, {}).get(domain, []))


def run_planned_comparisons(
    *,
    comparisons: Sequence[PlannedComparison],
    families: Sequence[MultiplicityFamily],
    runs_by_condition_domain: Mapping[str, Mapping[str, Sequence[RunResult]]],
    seed: int,
    n_resamples: int,
    alpha_default: float,
) -> tuple[ComparisonRow, ...]:
    alpha_of = {f.id: f.alpha for f in families}
    # 1) compute per-comparison p + CI; gather p-values per family.
    _N = float | None
    pre: dict[str, tuple[PlannedComparison, _N, _N, _N, _N]] = {}
    family_pvalues: dict[str, list[PValue]] = {}
    for i, comp in enumerate(comparisons):
        a = _arm(runs_by_condition_domain, comp.condition_a, comp.domain)
        b = _arm(runs_by_condition_domain, comp.condition_b, comp.domain)
        if not a or not b or set(task_reliability(a)) != set(task_reliability(b)):
            pre[comp.name] = (comp, None, None, None, None)  # skipped
            continue
        if comp.domain == "F":
            rel_a, rel_b = task_reliability(a), task_reliability(b)
            p = fisher_exact_two_sided(
                a_success=sum(rel_a.values()), a_n=len(rel_a),
                b_success=sum(rel_b.values()), b_n=len(rel_b),
            )
            point = sum(rel_b.values()) / len(rel_b) - sum(rel_a.values()) / len(rel_a)
            lo = hi = None  # F CI is the per-domain Clopper-Pearson, not a Delta CI
        else:
            # Per-comparison seed (seed+i): independent bootstrap sequences across
            # comparisons, while the CI and p-value of THIS comparison share the
            # same draws (same seed) so they stay monotone-consistent.
            comp_seed = seed + i
            ci = paired_pass_pow_k_diff_ci(
                a, b, n_resamples=n_resamples, seed=comp_seed, alpha=alpha_default
            )
            p = bootstrap_diff_p_value(a, b, n_resamples=n_resamples, seed=comp_seed)
            point, lo, hi = ci.point, ci.lo, ci.hi
        pre[comp.name] = (comp, point, lo, hi, p)
        family_pvalues.setdefault(comp.family_id, []).append(
            PValue(name=comp.name, p=p)
        )
    # 2) Holm per family.
    decisions: dict[str, HolmDecision] = {}
    for fid, pvs in family_pvalues.items():
        for d in holm_step_down(pvs, alpha=alpha_of.get(fid, alpha_default)):
            decisions[d.name] = d
    # 3) assemble rows in declared order.
    rows: list[ComparisonRow] = []
    for comp in comparisons:
        c, point, lo, hi, p = pre[comp.name]
        rows.append(
            ComparisonRow(
                comparison_name=comp.name, family_id=comp.family_id, domain=comp.domain,
                skipped=(p is None), delta_point=point, ci_lower=lo, ci_upper=hi,
                decision=decisions.get(comp.name),
            )
        )
    return tuple(rows)
