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
from agent_eval_lab.experiments.schema import ConditionDef
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

# The roster is now an explicit input (it lives in f-ablation-roster.toml, parsed
# by load_f_ablation_roster). The builder is pure: it carries whatever conditions
# + experiment_id it is given. These two stand in for a parsed roster.
_CONDS = (
    ConditionDef(condition_id="deepseek:deepseek-v4-pro", label="deepseek"),
    ConditionDef(condition_id="minimax:MiniMax-M3", label="minimax"),
)


def _build(experiment_id: str = "F-ablation-v2"):
    return build_f_ablation_spec(
        conditions=_CONDS,
        experiment_id=experiment_id,
        dataset_snapshot_hash="ds",
        pricing_snapshot_hash="pr",
    )


def test_builder_carries_the_given_conditions_and_experiment_id():
    spec = _build()
    assert tuple(spec.conditions) == _CONDS
    assert spec.experiment_id == "F-ablation-v2"


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
    spec = freeze_spec(_build())
    assert spec.spec_hash != ""
    assert verify_spec_hash(spec)
    assert spec.experiment_id == "F-ablation-v2"


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
    _ = freeze_spec(_build())
    assert verify_spec_hash(m1)
    # the two specs are different experiments with different hashes
    abl = freeze_spec(_build())
    assert abl.spec_hash != m1.spec_hash
    assert abl.experiment_id != m1.experiment_id
