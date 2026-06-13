"""Pure Pareto frontier over conditions: maximize success, minimize a cost axis
(cost_usd | rounds | tokens). A point is dominated iff another has success >=
AND cost <= with at least one strict. Identical points never dominate each other.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class ParetoPoint:
    condition_id: str
    success: float  # higher is better (pass^k)
    cost: float  # lower is better (usd | rounds | tokens)


def _dominates(p: ParetoPoint, q: ParetoPoint) -> bool:
    """p dominates q iff p is >= on success AND <= on cost, with >=1 strict."""
    no_worse = p.success >= q.success and p.cost <= q.cost
    strictly_better = p.success > q.success or p.cost < q.cost
    return no_worse and strictly_better


def pareto_frontier(points: Sequence[ParetoPoint]) -> tuple[ParetoPoint, ...]:
    frontier = [
        p for p in points if not any(_dominates(q, p) for q in points if q is not p)
    ]
    frontier.sort(key=lambda p: (p.cost, -p.success, p.condition_id))
    return tuple(frontier)
