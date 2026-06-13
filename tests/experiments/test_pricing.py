"""Tests for experiments/pricing.py — pricing loader, hash, per-condition cost."""

from pathlib import Path

import pytest

from agent_eval_lab.experiments.pricing import (
    PricePoint,
    PricingSnapshot,
    condition_cost_usd,
    load_pricing,
    pricing_snapshot_hash,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage

FIXTURES = Path(__file__).parent / "fixtures"


def _make_run(
    condition_id: str, prompt_tokens: int, completion_tokens: int
) -> RunResult:
    traj = Trajectory(
        schema_version="2",
        turns=(),
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=0.0,
        ),
        run_index=0,
        stop_reason="completed",
        rounds=1,
        wall_time_s=0.0,
        tool_call_counts={},
        safety_cap_bound=False,
        env_health=None,
    )
    return RunResult(
        task_id="t1",
        condition_id=condition_id,
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g1", passed=True, score=1.0, evidence={}, failure_reason=None
        ),
    )


def test_load_pricing_returns_snapshot() -> None:
    snap = load_pricing(FIXTURES / "pricing.json")
    assert isinstance(snap, PricingSnapshot)


def test_load_pricing_snapshot_date() -> None:
    snap = load_pricing(FIXTURES / "pricing.json")
    assert snap.snapshot_date == "2026-06-13"


def test_load_pricing_prices_mapping() -> None:
    snap = load_pricing(FIXTURES / "pricing.json")
    assert "deepseek:deepseek-v4-pro" in snap.prices
    pp = snap.prices["deepseek:deepseek-v4-pro"]
    assert isinstance(pp, PricePoint)
    assert pp.input_per_mtok == 1.74
    assert pp.output_per_mtok == 3.48


def test_pricing_snapshot_hash_is_sha256_hex() -> None:
    h = pricing_snapshot_hash(FIXTURES / "pricing.json")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_pricing_snapshot_hash_stable() -> None:
    h1 = pricing_snapshot_hash(FIXTURES / "pricing.json")
    h2 = pricing_snapshot_hash(FIXTURES / "pricing.json")
    assert h1 == h2


def test_condition_cost_usd_zero_for_free() -> None:
    snap = PricingSnapshot(
        snapshot_date="2026-01-01",
        prices={"free:free-model": PricePoint(input_per_mtok=0.0, output_per_mtok=0.0)},
    )
    runs = [_make_run("free:free-model", 1000, 500)]
    cost = condition_cost_usd(runs, "free:free-model", snap)
    assert cost == 0.0


def test_condition_cost_usd_correct_math() -> None:
    """1M prompt tokens at $1.74/Mtok + 1M completion at $3.48/Mtok = $5.22."""
    snap = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.74, output_per_mtok=3.48
            )
        },
    )
    # 1_000_000 prompt + 1_000_000 completion → (1.74 + 3.48) = 5.22
    runs = [_make_run("deepseek:deepseek-v4-pro", 1_000_000, 1_000_000)]
    cost = condition_cost_usd(runs, "deepseek:deepseek-v4-pro", snap)
    assert abs(cost - 5.22) < 1e-6


def test_condition_cost_usd_multiruns_sum_tokens() -> None:
    """Multiple runs for same condition: tokens are summed then priced."""
    snap = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.0, output_per_mtok=2.0
            )
        },
    )
    runs = [
        _make_run("deepseek:deepseek-v4-pro", 500_000, 250_000),
        _make_run("deepseek:deepseek-v4-pro", 500_000, 250_000),
    ]
    # total 1M prompt @ $1/Mtok + 0.5M completion @ $2/Mtok = $1 + $1 = $2
    cost = condition_cost_usd(runs, "deepseek:deepseek-v4-pro", snap)
    assert abs(cost - 2.0) < 1e-6


def test_condition_cost_usd_ignores_other_conditions(
) -> None:
    """LB-1 regression: tokens from OTHER conditions must not inflate the cost.
    Passing a mixed-condition result set must price only the target condition."""
    snap = PricingSnapshot(
        snapshot_date="2026-06-13",
        prices={
            "deepseek:deepseek-v4-pro": PricePoint(
                input_per_mtok=1.0, output_per_mtok=2.0
            ),
            "minimax:MiniMax-M3": PricePoint(
                input_per_mtok=99.0, output_per_mtok=99.0
            ),
        },
    )
    # target deepseek: 1M @ $1 + 1M @ $2 = $3; the minimax run must NOT count.
    runs = [
        _make_run("deepseek:deepseek-v4-pro", 1_000_000, 1_000_000),
        _make_run("minimax:MiniMax-M3", 1_000_000, 1_000_000),
    ]
    cost = condition_cost_usd(runs, "deepseek:deepseek-v4-pro", snap)
    assert abs(cost - 3.0) < 1e-6


def test_condition_cost_usd_raises_unknown_condition() -> None:
    snap = PricingSnapshot(snapshot_date="x", prices={})
    runs = [_make_run("unknown:model", 100, 50)]
    with pytest.raises(KeyError):
        condition_cost_usd(runs, "unknown:model", snap)
