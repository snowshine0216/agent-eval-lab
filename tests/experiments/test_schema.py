"""Tests for experiments/schema.py — frozen dataclasses, defaults, equality."""

import pytest

from agent_eval_lab.experiments.schema import (
    ConditionDef,
    DomainWeight,
    ExperimentResult,
    ExperimentRunRecord,
    ExperimentRunRef,
    ExperimentSpec,
    MetricDef,
    MultiplicityFamily,
    PlannedComparison,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _minimal_trajectory() -> Trajectory:
    return Trajectory(
        schema_version="2",
        turns=(),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
        rounds=1,
        wall_time_s=0.1,
        tool_call_counts={},
        safety_cap_bound=False,
        env_health=None,
    )


def _minimal_run_result() -> RunResult:
    return RunResult(
        task_id="t1",
        condition_id="deepseek:deepseek-v4-pro",
        run_index=0,
        trajectory=_minimal_trajectory(),
        grade=GradeResult(
            grader_id="g1", passed=True, score=1.0, evidence={}, failure_reason=None
        ),
    )


# ---------- DomainWeight ----------

def test_domain_weight_frozen() -> None:
    dw = DomainWeight(domain="F", weight=0.5)
    with pytest.raises(Exception):
        dw.weight = 0.9  # type: ignore[misc]  # frozen should raise


def test_domain_weight_equality() -> None:
    assert DomainWeight(domain="D", weight=0.3) == DomainWeight(domain="D", weight=0.3)


# ---------- ConditionDef ----------

def test_condition_def_default_skill_variant() -> None:
    c = ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek-noskill")
    assert c.skill_variant == "none"
    assert c.system_prompt_hash is None


def test_condition_def_frozen() -> None:
    c = ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek-noskill")
    with pytest.raises(Exception):
        c.label = "other"  # type: ignore[misc]


def test_condition_def_with_skill_variant() -> None:
    c = ConditionDef(
        condition_id="deepseek:deepseek-v4-pro",
        label="deepseek-skill",
        skill_variant="strategy_test_stripped",
        system_prompt_hash="abc123",
    )
    assert c.skill_variant == "strategy_test_stripped"
    assert c.system_prompt_hash == "abc123"


# ---------- MetricDef ----------

def test_metric_def_frozen() -> None:
    m = MetricDef(
        name="pass_pow_k",
        domain="F",
        primary=True,
        aggregation="pass_pow_k",
        ci_method="cluster_bootstrap",
        validity_mask=True,
        censoring_policy="failure",
    )
    with pytest.raises(Exception):
        m.primary = False  # type: ignore[misc]


def test_metric_def_composite_domain() -> None:
    m = MetricDef(
        name="macro_avg",
        domain="composite",
        primary=True,
        aggregation="mean",
        ci_method="none",
        validity_mask=False,
        censoring_policy="right_censored",
    )
    assert m.domain == "composite"


# ---------- MultiplicityFamily ----------

def test_multiplicity_family_frozen() -> None:
    f = MultiplicityFamily(
        id="fam1",
        description="main comparisons",
        correction="holm",
        alpha=0.05,
    )
    with pytest.raises(Exception):
        f.alpha = 0.1  # type: ignore[misc]


def test_multiplicity_family_equality() -> None:
    f1 = MultiplicityFamily(id="f", description="d", correction="holm", alpha=0.05)
    f2 = MultiplicityFamily(id="f", description="d", correction="holm", alpha=0.05)
    assert f1 == f2


# ---------- PlannedComparison ----------

def test_planned_comparison_frozen() -> None:
    pc = PlannedComparison(
        name="skill_effect_F",
        family_id="fam1",
        domain="F",
        condition_a="deepseek:deepseek-v4-pro",
        condition_b="deepseek:deepseek-v4-pro",
        metric_name="pass_pow_k",
    )
    with pytest.raises(Exception):
        pc.name = "other"  # type: ignore[misc]


# ---------- ExperimentSpec ----------

def _make_spec(**overrides) -> ExperimentSpec:
    defaults = dict(
        experiment_id="M1",
        k=3,
        repeats=1,
        safety_cap=12,
        max_invalid_rate=0.25,
        conditions=(
            ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="noskill"),
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
        ),
        macro_weights=(DomainWeight(domain="F", weight=1.0),),
        families=(
            MultiplicityFamily(
                id="main", description="d", correction="holm", alpha=0.05
            ),
        ),
        planned_comparisons=(),
        dataset_snapshot_hash="aabbcc",
        pricing_snapshot_hash="ddeeff",
        spec_hash="",
    )
    defaults.update(overrides)
    return ExperimentSpec(**defaults)


def test_experiment_spec_frozen() -> None:
    spec = _make_spec()
    with pytest.raises(Exception):
        spec.k = 5  # type: ignore[misc]


def test_experiment_spec_tuple_fields() -> None:
    spec = _make_spec()
    assert isinstance(spec.conditions, tuple)
    assert isinstance(spec.metrics, tuple)
    assert isinstance(spec.families, tuple)


# ---------- ExperimentResult ----------

def test_experiment_result_frozen() -> None:
    r = ExperimentResult(
        experiment_id="M1",
        spec_hash="abc",
        condition_id="deepseek:deepseek-v4-pro",
        domain="F",
        metric_name="pass_pow_k",
        estimate=0.6,
        ci_lower=0.4,
        ci_upper=0.8,
        ci_method="cluster_bootstrap",
        valid_run_count=30,
        invalid_run_count=2,
        void=False,
    )
    with pytest.raises(Exception):
        r.estimate = 0.9  # type: ignore[misc]


def test_experiment_result_nullable_ci() -> None:
    r = ExperimentResult(
        experiment_id="M1",
        spec_hash="abc",
        condition_id="deepseek:deepseek-v4-pro",
        domain="F",
        metric_name="pass_pow_k",
        estimate=0.6,
        ci_lower=None,
        ci_upper=None,
        ci_method="none",
        valid_run_count=30,
        invalid_run_count=0,
        void=False,
    )
    assert r.ci_lower is None
    assert r.ci_upper is None


# ---------- ExperimentRunRef / ExperimentRunRecord ----------

def test_experiment_run_ref_frozen() -> None:
    ref = ExperimentRunRef(
        run_uid="uid-001",
        artifact_sha256="deadbeef",
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    with pytest.raises(Exception):
        ref.run_uid = "other"  # type: ignore[misc]


def test_experiment_run_record_run_is_run_result() -> None:
    """ExperimentRunRecord.run must be the canonical RunResult owner."""
    ref = ExperimentRunRef(
        run_uid="uid-001",
        artifact_sha256="deadbeef",
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    run = _minimal_run_result()
    rec = ExperimentRunRecord(ref=ref, run=run)
    assert isinstance(rec.run, RunResult)
    assert rec.run.task_id == "t1"


def test_experiment_run_record_frozen() -> None:
    ref = ExperimentRunRef(
        run_uid="uid-001",
        artifact_sha256="deadbeef",
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    rec = ExperimentRunRecord(ref=ref, run=_minimal_run_result())
    with pytest.raises(Exception):
        rec.ref = ref  # type: ignore[misc]
