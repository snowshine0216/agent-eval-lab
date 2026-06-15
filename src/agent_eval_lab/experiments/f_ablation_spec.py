"""The frozen F-set ablation spec (§B.1 / §B.6 / §11.9). SEPARATE from production
m1_spec — building/freezing it never touches the committed frozen M1 specs.

Two frozen records:
  • an `ExperimentSpec` carrying the 4-model roster (condition_id=provider:model so
    pricing resolves — §B.2), one F primary pass^k metric, descriptive (no Holm,
    empty comparisons — §D.2). Frozen via the existing `freeze_spec` path.
  • an `AblationPolicy` carrying the harness-treatment knobs that are NOT
    ExperimentSpec fields (adding any would re-hash the schema and break m1 — see
    runners/round_budget.py docstring): the UNIFORM 40-round cap (production F stays
    20), the 12 task-arm ids, the 4 arm suffixes + 3 base tasks, and the seed for
    ablation_run_order. Hashed with the same canonical_json+sha256 as specs, so the
    40-round treatment + order are auditable (§9.2).

Pure: callers pass the dataset/pricing snapshot hashes. spec_hash/policy_hash are
left "" until the freeze functions write them.
"""

from __future__ import annotations

import dataclasses
import hashlib

from agent_eval_lab.experiments.ablation_order import ARMS
from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
)
from agent_eval_lab.experiments.spec_hash import canonical_json

# Seed for ablation_run_order, frozen here so the realized order is auditable.
ABLATION_SEED = 20260615

# The 4-model roster (§B.6). condition_id = provider:model (pricing — §B.2). The
# Qwen rung is the PROVISIONAL siliconflow id (labelled; spec Roster note).
_CONDITIONS: tuple[ConditionDef, ...] = (
    ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek"),
    ConditionDef(condition_id="glm:Pro/zai-org/GLM-5.1", label="glm"),
    ConditionDef(condition_id="minimax:MiniMax-M3", label="minimax"),
    ConditionDef(
        condition_id="siliconflow:Qwen/Qwen3.6-35B-A3B",
        label="qwen3.6-35b (PROVISIONAL)",
    ),
)

_BASE_TASKS: tuple[str, ...] = ("f1", "f2", "f3")
_ABLATION_MAX_ROUNDS = 40  # uniform across all four arms (§B.1); production F = 20.
_FAMILY_ID = "f-ablation-descriptive"


@dataclasses.dataclass(frozen=True, kw_only=True)
class AblationPolicy:
    """The harness-treatment knobs frozen alongside the ExperimentSpec but kept OFF
    the spec schema (no field change → m1 keeps verifying). policy_hash is written
    by freeze_ablation_policy (SHA256 over this record with policy_hash blanked)."""

    max_rounds: int
    seed: int
    k: int
    base_tasks: tuple[str, ...]
    arms: tuple[str, ...]
    task_arm_ids: tuple[str, ...]
    policy_hash: str = ""


def ablation_policy() -> AblationPolicy:
    """The (unfrozen) ablation policy: 40 rounds, seed, 12 task-arms, 4 arms."""
    task_arm_ids = tuple(f"f-{base}-{arm}" for base in _BASE_TASKS for arm in ARMS)
    return AblationPolicy(
        max_rounds=_ABLATION_MAX_ROUNDS,
        seed=ABLATION_SEED,
        k=5,
        base_tasks=_BASE_TASKS,
        arms=ARMS,
        task_arm_ids=task_arm_ids,
    )


def freeze_ablation_policy(policy: AblationPolicy) -> AblationPolicy:
    """Return a new policy with policy_hash = SHA256 over its canonical JSON (with
    policy_hash blanked). Idempotent — re-freezing yields the same hash."""
    blanked = dataclasses.replace(policy, policy_hash="")
    digest = hashlib.sha256(canonical_json(blanked).encode()).hexdigest()
    return dataclasses.replace(policy, policy_hash=digest)


def _metrics() -> tuple[MetricDef, ...]:
    return (
        MetricDef(
            name="pass_pow_k",
            domain="F",
            primary=True,
            aggregation="pass_pow_k",
            ci_method="binomial_exact",
            validity_mask=True,
            censoring_policy="failure",
        ),
        MetricDef(
            name="tokens",
            domain="F",
            primary=False,
            aggregation="median",
            ci_method="none",
            validity_mask=True,
            censoring_policy="right_censored",
        ),
        MetricDef(
            name="cost_usd",
            domain="F",
            primary=False,
            aggregation="median",
            ci_method="none",
            validity_mask=True,
            censoring_policy="right_censored",
        ),
    )


def build_f_ablation_spec(
    *, dataset_snapshot_hash: str, pricing_snapshot_hash: str
) -> ExperimentSpec:
    """Build the (unfrozen) F-ablation ExperimentSpec. spec_hash is left "" —
    freeze_spec writes it (same path as m1)."""
    family = MultiplicityFamily(
        id=_FAMILY_ID,
        description="F-set 2×2 harness-factor ablation — descriptive (no Holm, §D.2).",
        correction="holm",
        alpha=0.05,
    )
    return ExperimentSpec(
        experiment_id="F-ablation-v1",
        k=5,
        repeats=1,
        safety_cap=200,
        max_invalid_rate=0.40,
        conditions=_CONDITIONS,
        metrics=_metrics(),
        macro_weights=(DomainWeight(domain="F", weight=1.0),),
        families=(family,),
        planned_comparisons=(),  # descriptive only (§D.2); no confirmatory pairs.
        dataset_snapshot_hash=dataset_snapshot_hash,
        pricing_snapshot_hash=pricing_snapshot_hash,
        spec_hash="",
    )
