"""Pre-registration immutability — §18.2/D38.

All functions are pure; no I/O. The canonical JSON approach mirrors the
records/serialize.py pattern: sorted keys, fixed separators, no ambiguity.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping

from agent_eval_lab.experiments.schema import ExperimentSpec

# ---------------------------------------------------------------------------
# canonical_json — deterministic serialisation
# ---------------------------------------------------------------------------


def _to_plain(obj: object) -> object:
    """Recursively project a dataclass/Mapping/list/tuple/scalar to plain types.

    - dataclass → dict (sorted by field name for determinism)
    - Mapping    → dict (will be sorted by canonical_json)
    - list/tuple → list
    - None/bool/int/float/str → passthrough
    """
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _to_plain(getattr(obj, field.name))
            for field in dataclasses.fields(obj)  # type: ignore[arg-type]
        }
    if isinstance(obj, Mapping):
        return {k: _to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(item) for item in obj]
    return obj


def canonical_json(obj: object) -> str:
    """Deterministic JSON string: sorted keys, no extra whitespace.

    Handles dataclasses, Mappings, sequences, and scalars. Floats are emitted by
    json.dumps, which uses Python's shortest round-trippable float repr (0.05
    stays "0.05"), so the output is stable across runs without an explicit step.
    """
    plain = _to_plain(obj)
    return json.dumps(plain, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


# ---------------------------------------------------------------------------
# compute_spec_hash — SHA256 over spec without spec_hash field
# ---------------------------------------------------------------------------


def compute_spec_hash(spec: ExperimentSpec) -> str:
    """SHA256 hex over the canonical JSON of the spec with spec_hash blanked."""
    # Project to plain dict, then blank the spec_hash key.
    plain = _to_plain(spec)
    assert isinstance(plain, dict)
    plain["spec_hash"] = ""  # exclude this field from the hash
    serialised = json.dumps(
        plain, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    )
    return hashlib.sha256(serialised.encode()).hexdigest()


# ---------------------------------------------------------------------------
# validation helpers
# ---------------------------------------------------------------------------


def _validate_spec(spec: ExperimentSpec) -> None:
    """Raise ValueError with a clear message on any pre-registration violation."""
    if not spec.conditions:
        raise ValueError("ExperimentSpec.conditions must be non-empty")
    if not spec.metrics:
        raise ValueError("ExperimentSpec.metrics must be non-empty")

    # D38: exactly one primary metric per non-composite domain
    domain_primary_count: dict[str, int] = {}
    for m in spec.metrics:
        if m.domain == "composite":
            continue
        if m.primary:
            domain_primary_count[m.domain] = domain_primary_count.get(m.domain, 0) + 1

    # Also check domains that have metrics but no primary
    domains_with_metrics: set[str] = {
        m.domain for m in spec.metrics if m.domain != "composite"
    }
    for domain in domains_with_metrics:
        count = domain_primary_count.get(domain, 0)
        if count == 0:
            raise ValueError(
                f"Domain {domain!r} has metrics but no primary=True metric (D38)"
            )
        if count > 1:
            raise ValueError(
                f"Domain {domain!r} has {count} primary=True metrics; "
                "exactly one required (D38)"
            )

    # Every PlannedComparison.family_id must exist in families
    family_ids = {fam.id for fam in spec.families}
    for comp in spec.planned_comparisons:
        if comp.family_id not in family_ids:
            raise ValueError(
                f"PlannedComparison {comp.name!r} references unknown family_id "
                f"{comp.family_id!r}; known: {sorted(family_ids)}"
            )


# ---------------------------------------------------------------------------
# freeze_spec — idempotent; adds spec_hash
# ---------------------------------------------------------------------------


def freeze_spec(draft: ExperimentSpec) -> ExperimentSpec:
    """Validate and return a new spec with spec_hash populated.

    Idempotent: freezing an already-frozen spec yields the same hash.
    """
    _validate_spec(draft)
    new_hash = compute_spec_hash(draft)
    return dataclasses.replace(draft, spec_hash=new_hash)


# ---------------------------------------------------------------------------
# verify_spec_hash
# ---------------------------------------------------------------------------


def verify_spec_hash(spec: ExperimentSpec) -> bool:
    """Return True iff the stored spec_hash matches a fresh computation."""
    return compute_spec_hash(spec) == spec.spec_hash
