"""Derived cost: captured tokens x explicit prices. No stale hardcoded tables."""

from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.reliability import token_totals
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class TokenPrice:
    input_per_mtok: float
    output_per_mtok: float


def total_cost_usd(results: Sequence[RunResult], *, price: TokenPrice) -> float:
    prompt, completion = token_totals(results)
    return (
        prompt * price.input_per_mtok + completion * price.output_per_mtok
    ) / 1_000_000
