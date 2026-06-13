"""Builder for the real M1 ExperimentSpec (§8 / §18.2). Pure (no I/O): callers
pass the dataset/pricing snapshot hashes. spec_hash is left "" — freeze-spec
writes it. Conditions = the reachable roster (config.py PROVIDERS) plus the
PROVISIONAL SiliconFlow Qwen ladder (labelled provisional; condition ids stay
provisional until config.py gains the entries, §18.11). gpt-5.5 is omitted (the
network block is recorded in reports/final.EXCLUDED_CONDITIONS).
"""

from __future__ import annotations

from itertools import combinations

from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
    PlannedComparison,
)

# Reachable roster (condition_id = provider:model). The Qwen ladder ids are
# PROVISIONAL (siliconflow provider not yet in config.py) — labelled as such.
_CONDITIONS: tuple[ConditionDef, ...] = (
    ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek"),
    ConditionDef(condition_id="glm:Pro/zai-org/GLM-5.1", label="glm"),
    ConditionDef(condition_id="minimax:MiniMax-M3", label="minimax"),
    ConditionDef(condition_id="local:qwen3-8b", label="local-qwen3-8b"),
    ConditionDef(
        condition_id="siliconflow:Qwen/Qwen3.5-397B-A17B",
        label="qwen3.5-397b (PROVISIONAL)",
    ),
    ConditionDef(
        condition_id="siliconflow:Qwen/Qwen3.6-35B-A3B",
        label="qwen3.6-35b (PROVISIONAL)",
    ),
)

_FAMILY_ID = "m1-pairwise-D-primary"


def _metrics() -> tuple[MetricDef, ...]:
    def primary(domain, ci):
        return MetricDef(
            name="pass_pow_k",
            domain=domain,
            primary=True,
            aggregation="pass_pow_k",
            ci_method=ci,
            validity_mask=True,
            censoring_policy="failure",
        )

    def efficiency(name, domain):
        return MetricDef(
            name=name,
            domain=domain,
            primary=False,
            aggregation="median",
            ci_method="none",
            validity_mask=True,
            censoring_policy="right_censored",
        )

    metrics: list[MetricDef] = [
        primary("F", "binomial_exact"),
        primary("D", "cluster_bootstrap"),
        primary("B", "cluster_bootstrap"),
    ]
    for domain in ("F", "D", "B"):
        for name in ("rounds", "tokens", "cost_usd", "wall_time_s"):
            metrics.append(efficiency(name, domain))
    return tuple(metrics)


def build_m1_spec(
    *, dataset_snapshot_hash: str, pricing_snapshot_hash: str
) -> ExperimentSpec:
    family = MultiplicityFamily(
        id=_FAMILY_ID,
        description="Pairwise model comparisons on the D-domain primary pass^k.",
        correction="holm",
        alpha=0.05,
    )
    comparisons = tuple(
        PlannedComparison(
            name=f"{a.label}_vs_{b.label}",
            family_id=_FAMILY_ID,
            domain="D",
            condition_a=a.condition_id,
            condition_b=b.condition_id,
            metric_name="pass_pow_k",
        )
        for a, b in combinations(_CONDITIONS, 2)
    )
    return ExperimentSpec(
        experiment_id="M1-agentic-v1",
        k=5,
        repeats=1,
        safety_cap=200,
        max_invalid_rate=0.40,
        conditions=_CONDITIONS,
        metrics=_metrics(),
        macro_weights=(
            DomainWeight(domain="F", weight=1.0),
            DomainWeight(domain="D", weight=1.0),
            DomainWeight(domain="B", weight=1.0),
        ),
        families=(family,),
        planned_comparisons=comparisons,
        dataset_snapshot_hash=dataset_snapshot_hash,
        pricing_snapshot_hash=pricing_snapshot_hash,
        spec_hash="",
    )
