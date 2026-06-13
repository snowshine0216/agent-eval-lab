"""Holm step-down family correction + a bootstrap two-sided Delta pass^k p-value.

The p-value is the percentile-bootstrap analogue of a two-sided test on
Delta = pass^k(b) - pass^k(a), derived from the SAME paired cluster-bootstrap
draws reliability.py uses for the CI, so the p-value and the reported CI are
monotone-consistent (CI excludes 0 <=> p < alpha pre-correction). Seeded; no
global RNG. Stdlib only.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.reliability import task_reliability
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class PValue:
    name: str
    p: float


@dataclass(frozen=True, kw_only=True)
class HolmDecision:
    name: str
    p: float
    adjusted_p: float
    rejected: bool
    rank: int  # 0-based ascending


def bootstrap_diff_p_value(
    results_a: Sequence[RunResult],
    results_b: Sequence[RunResult],
    *,
    n_resamples: int,
    seed: int,
) -> float:
    """Two-sided percentile-bootstrap p for Delta = pass^k(b) - pass^k(a), PAIRED
    by task. Mirrors paired_pass_pow_k_diff_ci's resampling exactly (one task-id
    multiset applied to both arms) so p and CI cannot disagree."""
    rel_a = task_reliability(results_a)
    rel_b = task_reliability(results_b)
    if set(rel_a) != set(rel_b):
        raise ValueError(
            "paired p-value requires identical task-id universe; "
            f"got {sorted(rel_a)} vs {sorted(rel_b)}"
        )
    ids = list(rel_a)
    n = len(ids)
    rng = random.Random(seed)
    point = (sum(rel_b.values()) - sum(rel_a.values())) / n
    n_opposite = 0
    n_zero = 0
    for _ in range(n_resamples):
        drawn = [ids[rng.randrange(n)] for _ in range(n)]
        delta = (
            sum(rel_b[t] for t in drawn) - sum(rel_a[t] for t in drawn)
        ) / n
        # Tail mass on the side of 0 OPPOSITE the point estimate.
        if point > 0 and delta < 0:
            n_opposite += 1
        elif point < 0 and delta > 0:
            n_opposite += 1
        elif delta == 0:
            n_zero += 1
    if point == 0:
        return 1.0  # no observed effect -> maximal p
    p_one = (n_opposite + 0.5 * n_zero) / n_resamples
    return min(1.0, 2.0 * p_one)


def holm_step_down(
    pvalues: Sequence[PValue], *, alpha: float
) -> tuple[HolmDecision, ...]:
    """Holm-Bonferroni step-down within one family. Sort ascending; reject while
    p_(i) <= alpha/(m-i); STOP at the first non-rejection (all larger p retained).
    adjusted_p is the standard monotone form: cumulative-max of (m-i)*p_(i)."""
    m = len(pvalues)
    if m == 0:
        return ()
    ordered = sorted(enumerate(pvalues), key=lambda pair: pair[1].p)
    decisions: list[HolmDecision] = []
    still_rejecting = True
    running_max_adj = 0.0
    for i, (_, pv) in enumerate(ordered):
        threshold = alpha / (m - i)
        if still_rejecting and pv.p <= threshold:
            rejected = True
        else:
            still_rejecting = False
            rejected = False
        running_max_adj = max(running_max_adj, min(1.0, (m - i) * pv.p))
        decisions.append(
            HolmDecision(
                name=pv.name,
                p=pv.p,
                adjusted_p=running_max_adj,
                rejected=rejected,
                rank=i,
            )
        )
    return tuple(decisions)
