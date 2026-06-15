from pathlib import Path

import pytest

from agent_eval_lab.experiments.f_ablation_spec import (
    ABLATION_SEED,
    AblationPolicy,
    ablation_policy,
    build_f_ablation_spec,
    freeze_ablation_policy,
)
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.spec_hash import (
    canonical_json,
    freeze_spec,
    verify_spec_hash,
)

_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)

requires_store = pytest.mark.skipif(
    not (_STORE / "golden-files" / "f1.held_out.test.js").exists(),
    reason="local web-dossier golden store required",
)


def test_roster_is_the_four_design_models():
    spec = build_f_ablation_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    ids = [c.condition_id for c in spec.conditions]
    assert ids == [
        "deepseek:deepseek-v4-pro",
        "glm:Pro/zai-org/GLM-5.1",
        "minimax:MiniMax-M3",
        "siliconflow:Qwen/Qwen3.6-35B-A3B",
    ]
    # the PROVISIONAL roster member is labelled (spec Roster note)
    qwen = next(c for c in spec.conditions if c.condition_id.startswith("siliconflow"))
    assert "PROVISIONAL" in qwen.label


def test_policy_records_40_rounds_12_arms_and_seed():
    policy = ablation_policy()
    assert isinstance(policy, AblationPolicy)
    assert policy.max_rounds == 40
    assert policy.seed == ABLATION_SEED
    assert policy.k == 5
    assert policy.base_tasks == ("f1", "f2", "f3")
    assert policy.arms == ("bare", "prompt", "feedback", "both")
    # the 12 task-arm ids are exactly f-{base}-{arm} for all 3 bases × 4 arms
    expected_arm_ids = {
        f"f-{base}-{arm}"
        for base in ("f1", "f2", "f3")
        for arm in ("bare", "prompt", "feedback", "both")
    }
    assert set(policy.task_arm_ids) == expected_arm_ids
    assert len(policy.task_arm_ids) == 12


@requires_store
def test_policy_task_arm_ids_match_dataset_builder():
    from agent_eval_lab.datasets.f_tasks import build_f_task_arms

    policy = ablation_policy()
    arm_ids = {t.id for t in build_f_task_arms(evaluator_store=_STORE)}
    assert set(policy.task_arm_ids) == arm_ids


def test_spec_freezes_and_verifies_independently_of_m1():
    spec = freeze_spec(
        build_f_ablation_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    assert spec.spec_hash != ""
    assert verify_spec_hash(spec)
    assert spec.experiment_id == "F-ablation-v1"


def test_freeze_ablation_policy_is_deterministic_and_hashes_the_seed():
    frozen = freeze_ablation_policy(ablation_policy())
    assert frozen.policy_hash != ""
    # re-freezing is idempotent
    assert freeze_ablation_policy(frozen).policy_hash == frozen.policy_hash
    # the seed is inside the hashed payload: a different seed ⇒ different hash
    from dataclasses import replace

    other = freeze_ablation_policy(replace(ablation_policy(), seed=ABLATION_SEED + 1))
    assert other.policy_hash != frozen.policy_hash
    # the hash is over the canonical JSON with policy_hash blanked
    assert "policy_hash" in canonical_json(frozen)


def test_building_the_ablation_spec_does_not_touch_m1():
    # m1's frozen spec still verifies after we build/freeze the ablation spec.
    m1 = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    _ = freeze_spec(
        build_f_ablation_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    assert verify_spec_hash(m1)
    # the two specs are different experiments with different hashes
    abl = freeze_spec(
        build_f_ablation_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    assert abl.spec_hash != m1.spec_hash
    assert abl.experiment_id != m1.experiment_id
