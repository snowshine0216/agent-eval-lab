"""Tests for experiments/spec_hash.py.

Covers: determinism, exclusion of spec_hash, idempotency, and validation.
"""

import json

import pytest

from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
    PlannedComparison,
)
from agent_eval_lab.experiments.spec_hash import (
    canonical_json,
    compute_spec_hash,
    freeze_spec,
    verify_spec_hash,
)


def _make_spec(**overrides) -> ExperimentSpec:
    defaults = dict(
        experiment_id="M1",
        k=3,
        repeats=1,
        safety_cap=12,
        max_invalid_rate=0.25,
        conditions=(
            ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="noskill"),
            ConditionDef(
                condition_id="glm:Pro/zai-org/GLM-5.1",
                label="glm-noskill",
            ),
        ),
        metrics=(
            MetricDef(
                name="pass_pow_k",
                domain="F",
                primary=True,
                aggregation="pass_pow_k",
                ci_method="cluster_bootstrap",
                validity_mask=True,
                censoring_policy="failure",
            ),
            MetricDef(
                name="pass_pow_k_D",
                domain="D",
                primary=True,
                aggregation="pass_pow_k",
                ci_method="cluster_bootstrap",
                validity_mask=True,
                censoring_policy="failure",
            ),
        ),
        macro_weights=(
            DomainWeight(domain="F", weight=0.5),
            DomainWeight(domain="D", weight=0.5),
        ),
        families=(
            MultiplicityFamily(
                id="main", description="main", correction="holm", alpha=0.05
            ),
        ),
        planned_comparisons=(
            PlannedComparison(
                name="glm_vs_deepseek_F",
                family_id="main",
                domain="F",
                condition_a="deepseek:deepseek-v4-pro",
                condition_b="glm:Pro/zai-org/GLM-5.1",
                metric_name="pass_pow_k",
            ),
        ),
        dataset_snapshot_hash="aabb",
        pricing_snapshot_hash="ccdd",
        spec_hash="",
    )
    defaults.update(overrides)
    return ExperimentSpec(**defaults)


# ---------- canonical_json ----------


def test_canonical_json_is_sorted_keys() -> None:
    d = {"z": 1, "a": 2, "m": 3}
    result = canonical_json(d)
    parsed = json.loads(result)
    assert list(parsed.keys()) == sorted(parsed.keys())


def test_canonical_json_deterministic_across_dict_order() -> None:
    d1 = {"z": 1, "a": 2}
    d2 = {"a": 2, "z": 1}
    assert canonical_json(d1) == canonical_json(d2)


def test_canonical_json_nested_dicts_sorted() -> None:
    obj = {"outer": {"z": 9, "a": 1}}
    result = canonical_json(obj)
    outer_val = json.loads(result)["outer"]
    assert list(outer_val.keys()) == sorted(outer_val.keys())


def test_canonical_json_no_extra_whitespace() -> None:
    result = canonical_json({"a": 1})
    assert "\n" not in result
    assert "  " not in result


def test_canonical_json_on_dataclass() -> None:
    """canonical_json must handle dataclasses by converting to dict."""
    dw = DomainWeight(domain="F", weight=0.5)
    result = canonical_json(dw)
    assert "domain" in result
    assert "weight" in result


# ---------- compute_spec_hash ----------


def test_compute_spec_hash_returns_sha256_hex() -> None:
    spec = _make_spec()
    h = compute_spec_hash(spec)
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_compute_spec_hash_excludes_spec_hash_field() -> None:
    """Two specs differing ONLY in spec_hash should hash identically."""
    spec_a = _make_spec(spec_hash="")
    spec_b = _make_spec(spec_hash="some_previous_hash")
    assert compute_spec_hash(spec_a) == compute_spec_hash(spec_b)


def test_compute_spec_hash_sensitive_to_k() -> None:
    spec_k3 = _make_spec(k=3)
    spec_k5 = _make_spec(k=5)
    assert compute_spec_hash(spec_k3) != compute_spec_hash(spec_k5)


def test_compute_spec_hash_deterministic() -> None:
    spec = _make_spec()
    assert compute_spec_hash(spec) == compute_spec_hash(spec)


# ---------- freeze_spec ----------


def test_freeze_spec_writes_spec_hash() -> None:
    draft = _make_spec(spec_hash="")
    frozen = freeze_spec(draft)
    assert len(frozen.spec_hash) == 64


def test_freeze_spec_idempotent() -> None:
    """Freezing a frozen spec yields the same hash."""
    draft = _make_spec(spec_hash="")
    frozen1 = freeze_spec(draft)
    frozen2 = freeze_spec(frozen1)
    assert frozen1.spec_hash == frozen2.spec_hash


def test_freeze_spec_returns_new_object() -> None:
    draft = _make_spec(spec_hash="")
    frozen = freeze_spec(draft)
    assert frozen is not draft
    assert draft.spec_hash == ""
    assert frozen.spec_hash != ""


# ---------- verify_spec_hash ----------


def test_verify_spec_hash_true_for_frozen() -> None:
    frozen = freeze_spec(_make_spec())
    assert verify_spec_hash(frozen) is True


def test_verify_spec_hash_false_for_tampered() -> None:
    frozen = freeze_spec(_make_spec())
    # replace spec_hash with a bogus value
    from dataclasses import replace

    tampered = replace(frozen, spec_hash="0" * 64)
    assert verify_spec_hash(tampered) is False


# ---------- validation in freeze_spec ----------


def test_freeze_spec_rejects_zero_primary_metrics_for_domain() -> None:
    """A domain with no primary metric must raise."""
    no_primary = _make_spec(
        metrics=(
            MetricDef(
                name="pass_pow_k",
                domain="F",
                primary=False,  # no primary for F
                aggregation="pass_pow_k",
                ci_method="cluster_bootstrap",
                validity_mask=True,
                censoring_policy="failure",
            ),
        )
    )
    with pytest.raises(ValueError, match="primary"):
        freeze_spec(no_primary)


def test_freeze_spec_rejects_two_primary_metrics_same_domain() -> None:
    """Two primary=True metrics for the same domain must raise (D38)."""
    two_primary = _make_spec(
        metrics=(
            MetricDef(
                name="m1",
                domain="F",
                primary=True,
                aggregation="pass_pow_k",
                ci_method="cluster_bootstrap",
                validity_mask=True,
                censoring_policy="failure",
            ),
            MetricDef(
                name="m2",
                domain="F",
                primary=True,
                aggregation="mean",
                ci_method="none",
                validity_mask=False,
                censoring_policy="right_censored",
            ),
        )
    )
    with pytest.raises(ValueError, match="primary"):
        freeze_spec(two_primary)


def test_freeze_spec_rejects_dangling_family_id() -> None:
    """A PlannedComparison referencing a non-existent family_id must raise."""
    dangling = _make_spec(
        planned_comparisons=(
            PlannedComparison(
                name="comp",
                family_id="nonexistent",
                domain="F",
                condition_a="deepseek:deepseek-v4-pro",
                condition_b="glm:Pro/zai-org/GLM-5.1",
                metric_name="pass_pow_k",
            ),
        )
    )
    with pytest.raises(ValueError, match="family_id"):
        freeze_spec(dangling)


def test_freeze_spec_rejects_empty_conditions() -> None:
    with pytest.raises(ValueError, match="condition"):
        freeze_spec(_make_spec(conditions=()))


def test_freeze_spec_rejects_empty_metrics() -> None:
    with pytest.raises(ValueError, match="metric"):
        freeze_spec(_make_spec(metrics=()))
