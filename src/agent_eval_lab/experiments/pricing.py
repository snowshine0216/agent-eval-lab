"""Pricing snapshot loader + per-condition cost derivation (§18.11).

Reuses metrics/cost.py token×price math via token_totals. The runner and
records layers are NOT modified; cost is always derived in post-processing.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from agent_eval_lab.metrics.reliability import token_totals
from agent_eval_lab.records.grade import RunResult

# ---------------------------------------------------------------------------
# Pricing dataclasses (frozen)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, kw_only=True)
class PricePoint:
    input_per_mtok: float
    output_per_mtok: float


@dataclass(frozen=True, kw_only=True)
class PricingSnapshot:
    snapshot_date: str
    prices: Mapping[str, PricePoint]


# ---------------------------------------------------------------------------
# I/O: load_pricing + pricing_snapshot_hash
# ---------------------------------------------------------------------------

def load_pricing(path: Path) -> PricingSnapshot:
    """Load a pricing.json file and return a typed PricingSnapshot."""
    data = json.loads(path.read_text(encoding="utf-8"))
    prices = {
        condition_id: PricePoint(
            input_per_mtok=float(entry["input_per_mtok"]),
            output_per_mtok=float(entry["output_per_mtok"]),
        )
        for condition_id, entry in data["prices"].items()
    }
    return PricingSnapshot(
        snapshot_date=data["snapshot_date"],
        prices=prices,
    )


def pricing_snapshot_hash(path: Path) -> str:
    """SHA256 hex over the raw file bytes (stable, order-independent)."""
    raw = path.read_bytes()
    return hashlib.sha256(raw).hexdigest()


# ---------------------------------------------------------------------------
# Pure cost derivation — reuses metrics/cost.py token_totals
# ---------------------------------------------------------------------------

def condition_cost_usd(
    results: Sequence[RunResult],
    condition_id: str,
    snapshot: PricingSnapshot,
) -> float:
    """Total cost in USD for all runs under condition_id.

    Raises:
        KeyError: if condition_id is not in snapshot.prices.
    """
    price = snapshot.prices[condition_id]  # raises KeyError if unknown
    # Only this condition's runs (LB-1): a mixed-condition result set must not
    # let one condition's tokens inflate another's cost.
    own = [r for r in results if r.condition_id == condition_id]
    prompt_tokens, completion_tokens = token_totals(own)
    return (
        prompt_tokens * price.input_per_mtok
        + completion_tokens * price.output_per_mtok
    ) / 1_000_000
