"""Experiment types — verbatim §18.3 contract.

All types are frozen dataclasses (immutable value objects). Do NOT modify the
field signatures; downstream items (003–007) depend on this exact shape.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from agent_eval_lab.records.grade import RunResult

Domain = Literal["F", "D", "B"]


@dataclass(frozen=True, kw_only=True)
class DomainWeight:
    domain: Domain
    weight: float


@dataclass(frozen=True, kw_only=True)
class ConditionDef:
    condition_id: str  # provider:model
    label: str  # e.g. "deepseek-noskill", "deepseek-skill"
    skill_variant: Literal["none", "strategy_test_stripped"] = "none"
    # SHA256 of injected system prompt at freeze time
    system_prompt_hash: str | None = None


@dataclass(frozen=True, kw_only=True)
class MetricDef:
    name: str
    domain: Domain | Literal["composite"]
    primary: bool  # exactly one per domain (D38)
    aggregation: Literal["pass_pow_k", "mean", "median", "point_estimate"]
    ci_method: Literal["cluster_bootstrap", "binomial_exact", "none"]
    validity_mask: bool
    censoring_policy: Literal["failure", "right_censored"]


@dataclass(frozen=True, kw_only=True)
class MultiplicityFamily:
    id: str
    description: str
    correction: Literal["holm", "none"]
    alpha: float


@dataclass(frozen=True, kw_only=True)
class PlannedComparison:
    name: str
    family_id: str  # joins to MultiplicityFamily.id
    domain: Domain
    condition_a: str  # condition_id
    condition_b: str  # condition_id; effect = metric(b) − metric(a)
    metric_name: str


@dataclass(frozen=True, kw_only=True)
class ExperimentSpec:
    experiment_id: str
    k: int
    repeats: int
    safety_cap: int
    max_invalid_rate: float
    conditions: tuple[ConditionDef, ...]
    metrics: tuple[MetricDef, ...]
    macro_weights: tuple[DomainWeight, ...]
    families: tuple[MultiplicityFamily, ...]
    planned_comparisons: tuple[PlannedComparison, ...]
    dataset_snapshot_hash: str  # SHA256 over sorted canonical JSON of all task defs
    pricing_snapshot_hash: str  # SHA256 over evaluator-only/pricing.json
    spec_hash: str  # SHA256 of spec excluding this field; written by freeze-spec


@dataclass(frozen=True, kw_only=True)
class ExperimentResult:
    experiment_id: str
    spec_hash: str
    condition_id: str
    domain: Domain | Literal["composite"]
    metric_name: str
    estimate: float
    ci_lower: float | None
    ci_upper: float | None
    ci_method: str
    valid_run_count: int
    invalid_run_count: int
    void: bool


@dataclass(frozen=True, kw_only=True)
class ExperimentRunRef:
    run_uid: str
    artifact_sha256: str
    domain: Domain
    repeat_index: int
    attempt_index: int  # 0 = first attempt; increments on invalid replacement trials


@dataclass(frozen=True, kw_only=True)
class ExperimentRunRecord:
    ref: ExperimentRunRef
    run: RunResult  # canonical owner of task_id/condition_id/Trajectory/GradeResult
