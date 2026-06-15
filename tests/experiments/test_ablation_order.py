from collections import Counter

from agent_eval_lab.experiments.ablation_order import (
    ARMS,
    RunUnit,
    ablation_run_order,
)

_MODELS = ("deepseek:deepseek-v4-pro", "glm:Pro/zai-org/GLM-5.1")
_BASES = ("f1", "f2", "f3")


def test_total_coverage_each_unit_exactly_once_at_k5():
    order = ablation_run_order(seed=20260615, models=_MODELS, base_tasks=_BASES, k=5)
    # 4 arms × 2 models × 3 bases × 5 reps = 120 here; 240 with the 4-model roster.
    assert len(order) == 4 * len(_MODELS) * len(_BASES) * 5
    counts = Counter((u.model, u.base_task, u.arm, u.repetition) for u in order)
    assert all(c == 1 for c in counts.values())  # no dup
    # exactly each (model × base × arm × rep) present once
    expected = {
        (m, b, a, r) for m in _MODELS for b in _BASES for a in ARMS for r in range(5)
    }
    assert set(counts) == expected


def test_task_id_encodes_the_arm():
    order = ablation_run_order(seed=1, models=_MODELS, base_tasks=_BASES, k=2)
    sample = order[0]
    assert sample.task_id == f"f-{sample.base_task}-{sample.arm}"
    assert isinstance(sample, RunUnit)


def test_same_seed_is_identical():
    a = ablation_run_order(seed=7, models=_MODELS, base_tasks=_BASES, k=5)
    b = ablation_run_order(seed=7, models=_MODELS, base_tasks=_BASES, k=5)
    assert a == b


def test_different_seed_differs():
    a = ablation_run_order(seed=7, models=_MODELS, base_tasks=_BASES, k=5)
    b = ablation_run_order(seed=8, models=_MODELS, base_tasks=_BASES, k=5)
    assert a != b


def test_no_wall_clock_dependence_two_calls_equal():
    # A wall-clock or unseeded RNG would make repeated calls diverge.
    assert ablation_run_order(
        seed=42, models=_MODELS, base_tasks=_BASES, k=3
    ) == ablation_run_order(seed=42, models=_MODELS, base_tasks=_BASES, k=3)


def test_arms_interleaved_within_each_block_not_arm_grouped():
    # Within any (model, base, rep) block the 4 consecutive units are exactly the
    # 4 arms (a contiguous shuffled block), and across the whole order at least one
    # block is NOT in the canonical ARMS order (proves a real shuffle).
    order = ablation_run_order(seed=20260615, models=_MODELS, base_tasks=_BASES, k=5)
    blocks = [order[i : i + 4] for i in range(0, len(order), 4)]
    shuffled_seen = False
    for block in blocks:
        keys = {(u.model, u.base_task, u.repetition) for u in block}
        assert len(keys) == 1  # one block = one (model, base, rep)
        assert {u.arm for u in block} == set(ARMS)  # all 4 arms, interleaved
        if tuple(u.arm for u in block) != ARMS:
            shuffled_seen = True
    assert shuffled_seen  # the RNG actually reorders arms within blocks
