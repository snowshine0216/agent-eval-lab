# Item 006 — `run-f-ablation` driver + frozen `f_ablation_spec` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the final orchestration the F-set ablation needs — a pure seeded block-randomized `ablation_run_order`, a frozen `f_ablation_spec` (40-round policy + 12 task-arms + 4-model roster + seed), and a `run-f-ablation` CLI driver that consumes that order and writes one artifact per condition plus a realized-order sidecar — **without ever triggering a paid provider call in this item, its tests, or CI**.

**Architecture:** Three net-new pure modules + one CLI driver + CLI wiring. `experiments/ablation_order.py` holds the pure `ablation_run_order(seed, models, base_tasks, k)` (seeded `random.Random`, no wall-clock) that interleaves all four arms within each `(model, base-task, rep)` block. `experiments/f_ablation_spec.py` builds an `ExperimentSpec` (4-model roster, k=5) frozen via the **existing** `freeze_spec` path plus a separate `AblationPolicy` frozen dataclass (40-round, arm suffixes, seed) hashed by the same `canonical_json`+sha256 helper — so **no `ConditionDef`/`ExperimentSpec` schema field is added** and m1's frozen specs keep verifying. The `run-f-ablation` driver (`cli._run_f_ablation_command`) walks the frozen order, calls the injected/real `run_fn` per unit, buffers `RunResult`s per condition, writes one `runs-ablation-{slug}-F.jsonl` per condition + a realized-order sidecar. Every test injects a fake `run_fn`; a `--dry-run` flag writes the order with **zero** `run_fn` calls.

**Tech Stack:** Python 3.13, frozen dataclasses, `random.Random(seed)` (the repo's only seeded-RNG idiom — `metrics/reliability.py:101`), pytest (`-o addopts=""`), ruff (`ruff check .` + `ruff format --check .`). Pure FP house style (CLAUDE.md): the order is a pure function of `(seed, models, base_tasks, k)`; all I/O is at the CLI edge.

---

## Background — what already exists (do NOT rebuild)

Confirmed by study; these are the seams the driver consumes:

- **`datasets/f_tasks.build_f_task_arms(*, evaluator_store)`** (003) → the 12 `Task`s with ids `f-f1-bare`, `f-f1-prompt`, `f-f1-feedback`, `f-f1-both`, `f-f2-*`, `f-f3-*`. Each arm carries `metadata.max_rounds=40` and `initial_state["factor_p"/"factor_v"/"context_paths"]`.
- **`runners/f_candidate.build_candidate_tree(task, *, repo)`** (004 enriched) → seeds `context_paths` into the tree, byte-identical across arms.
- **`runners/f_candidate.make_f_run_fn(...)`** (003/005) → builds the per-attempt driver; routes V arms to the sandboxed executor on macOS, refuses off-macOS. **This is the only place a provider call is made** — the driver passes a `run_fn` built here OR an injected fake.
- **`runners/f_candidate.run_f_candidate(*, tasks, k, condition_id, build_tree_fn, run_fn)`** → yields one `ReplacementOutcome` per task (k attempts each). The current `_run_f_command` (cli.py:870) drives ALL k attempts of ALL tasks per condition with no cross-condition order. **006 does NOT call `run_f_candidate`** — it needs unit-level (model × arm × rep) granularity to interleave, so it drives `make_edit_task` + `run_fn` directly (see Task 3).
- **`make_edit_task(task, *, base_tree)`** + **`_grade(task, trajectory, *, condition_id, run_index)`** in `f_candidate.py` → recast an arm to an edit task and grade one attempt's trajectory. `_grade` is module-private; Task 3 adds a thin public `grade_f_attempt` wrapper to `f_candidate.py` so the driver does not reach into a `_`-name.
- **`experiments/spec_hash`**: `canonical_json(obj)` (handles ANY dataclass via `_to_plain`), `compute_spec_hash`, `freeze_spec`, `verify_spec_hash`. The 40-round/seed/arms are NOT `ExperimentSpec` fields, so they ride a separate `AblationPolicy` dataclass hashed with the same `canonical_json` (see Task 2).
- **`reports/m1` / `metrics/reliability.pass_pow_k`** group by `run.task_id` (confirmed `reliability.py:46` — `by_task.setdefault(run.task_id, ...)`). Because the arm rides `task_id`, per-arm pass^k falls out of one-artifact-per-condition with **no report change**. Task 6 asserts this; it changes nothing.
- **`cli._slug`, `cli._append_runs`, `cli.condition_id`, `cli.PROVIDERS`, `cli.resolve_proxy`** — reused by the driver exactly as `_run_f_command` uses them.

## File Structure (decomposition)

- **Create** `src/agent_eval_lab/experiments/ablation_order.py` — pure `RunUnit` dataclass + `ablation_run_order(...)`. No I/O. ~50 lines.
- **Create** `src/agent_eval_lab/experiments/f_ablation_spec.py` — `AblationPolicy` dataclass, `ABLATION_SEED`, `ablation_policy()`, `build_f_ablation_spec(...)`, `freeze_ablation_policy(...)`. Pure (no I/O). ~80 lines.
- **Modify** `src/agent_eval_lab/runners/f_candidate.py` — add public `grade_f_attempt(...)` wrapper over `_grade` (so the driver doesn't import a `_`-name). No behavior change.
- **Modify** `src/agent_eval_lab/cli.py` — add `_run_f_ablation_command(...)`, the `run-f-ablation` subparser, the dispatch line, and the imports.
- **Create** `tests/experiments/test_ablation_order.py` — coverage / no-dup / determinism / different-seed / interleaving tests.
- **Create** `tests/experiments/test_f_ablation_spec.py` — roster / 40-round / 12-arm / freeze+verify / m1-untouched tests.
- **Create** `tests/cli/test_run_f_ablation.py` — driver tests with a fake `run_fn`: consumes order, one artifact per condition, sidecar written, NO provider call, `--dry-run` makes zero `run_fn` calls.

---

## Task 1: Pure `ablation_run_order`

**Files:**
- Create: `src/agent_eval_lab/experiments/ablation_order.py`
- Test: `tests/experiments/test_ablation_order.py`

The arms are the 4 fixed suffixes. A **unit** is `(model, base_task, arm, rep)`. A **block** is one `(model, base_task, rep)` — it holds exactly the 4 arms, shuffled together (interleaved) by the seeded RNG. Blocks are emitted in a stable nested order (model, base_task, rep); within each block the 4 arms are shuffled. This guarantees: total coverage = `len(models) × len(base_tasks) × k × 4`; arms never group across a block (provider drift across a block can't align with one arm); determinism from the single seeded RNG advanced in a fixed traversal.

- [ ] **Step 1: Write the failing tests**

```python
# tests/experiments/test_ablation_order.py
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
        (m, b, a, r)
        for m in _MODELS
        for b in _BASES
        for a in ARMS
        for r in range(5)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/experiments/test_ablation_order.py -o addopts="" -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.experiments.ablation_order'`.

- [ ] **Step 3: Write the pure implementation**

```python
# src/agent_eval_lab/experiments/ablation_order.py
"""Pure seeded block-randomized execution order for the F-set ablation (§B.7).

A *unit* is one (model, base-task, arm, repetition) attempt. A *block* is one
(model, base-task, repetition); it holds exactly the four arms. Within each block
the four arms are SHUFFLED TOGETHER (interleaved), so provider drift across a
block cannot align with one arm and masquerade as a P/V effect (§B.7). Blocks are
emitted in a fixed nested traversal (model, base-task, rep); the single seeded RNG
is advanced in that fixed traversal, so the order is a pure deterministic function
of (seed, models, base_tasks, k) — no wall-clock, no module-level RNG (§11.9).
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

# The 2×2 arms (003 §B.1), in canonical order. The arm rides the task_id (§B.2).
ARMS: tuple[str, ...] = ("bare", "prompt", "feedback", "both")


@dataclass(frozen=True, kw_only=True)
class RunUnit:
    """One scheduled attempt. `model` is the condition_id (provider:model); the arm
    is encoded in `task_id` (`f-{base_task}-{arm}`), never a separate field."""

    model: str
    base_task: str
    arm: str
    repetition: int

    @property
    def task_id(self) -> str:
        return f"f-{self.base_task}-{self.arm}"


def ablation_run_order(
    *, seed: int, models: Sequence[str], base_tasks: Sequence[str], k: int
) -> tuple[RunUnit, ...]:
    """Deterministic block-randomized order over (model × base-task × arm × rep).

    Coverage: exactly each (model, base_task, arm, repetition) once — length
    `len(models) × len(base_tasks) × k × len(ARMS)`. Within every (model, base, rep)
    block the four arms are shuffled together (interleaved). Same seed ⇒ identical
    order; different seed ⇒ (almost surely) different order. Pure: no I/O, no clock.
    """
    rng = random.Random(seed)
    units: list[RunUnit] = []
    for model in models:
        for base in base_tasks:
            for rep in range(k):
                block = [
                    RunUnit(model=model, base_task=base, arm=arm, repetition=rep)
                    for arm in ARMS
                ]
                rng.shuffle(block)  # interleave the 4 arms WITHIN this block
                units.extend(block)
    return tuple(units)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/experiments/test_ablation_order.py -o addopts="" -q`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/experiments/ablation_order.py tests/experiments/test_ablation_order.py
git commit -m "feat(006): pure seeded block-randomized ablation_run_order"
```

---

## Task 2: Frozen `f_ablation_spec` (40-round policy + 12 arms + 4-model roster + seed)

**Files:**
- Create: `src/agent_eval_lab/experiments/f_ablation_spec.py`
- Test: `tests/experiments/test_f_ablation_spec.py`

The 4-model roster (§B.6: deepseek-v4-pro, GLM-5.1, MiniMax-M3, Qwen3.6-35B) rides the existing `ExperimentSpec.conditions` (`condition_id=provider:model` so pricing resolves — §B.2), with a single F primary `pass_pow_k` (binomial_exact) metric and an empty `planned_comparisons`/single family (the ablation is descriptive — §D.2; `_validate_spec` requires one primary per domain with metrics and that every comparison's family exists, both satisfied). The 40-round policy, the 4 arm suffixes, and the seed are NOT `ExperimentSpec` fields (adding any would re-hash the schema and break m1 — §B.2 / round_budget.py docstring), so they ride a **separate** `AblationPolicy` frozen dataclass hashed via the same `canonical_json`+sha256 used for specs. Qwen3.6-35B's id is the PROVISIONAL siliconflow id, labelled provisional (spec Roster note).

- [ ] **Step 1: Write the failing tests**

```python
# tests/experiments/test_f_ablation_spec.py
from agent_eval_lab.datasets.f_tasks import build_f_task_arms
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
    # the 12 task-arms named in the policy match the dataset builder exactly
    from pathlib import Path

    arm_ids = {t.id for t in build_f_task_arms(evaluator_store=Path("/nonexistent"))}
    assert set(policy.task_arm_ids) == arm_ids
    assert len(policy.task_arm_ids) == 12


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
    m1 = freeze_spec(build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr"))
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/experiments/test_f_ablation_spec.py -o addopts="" -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.experiments.f_ablation_spec'`.

- [ ] **Step 3: Write the implementation**

```python
# src/agent_eval_lab/experiments/f_ablation_spec.py
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
    task_arm_ids = tuple(
        f"f-{base}-{arm}" for base in _BASE_TASKS for arm in ARMS
    )
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/experiments/test_f_ablation_spec.py -o addopts="" -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Confirm m1's committed frozen spec still verifies (regression)**

Run: `python -m pytest tests/experiments/test_m1_spec.py tests/experiments/test_spec_hash.py -o addopts="" -q`
Expected: PASS (all existing m1/spec_hash tests green — we added a sibling builder, changed no shared code).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/experiments/f_ablation_spec.py tests/experiments/test_f_ablation_spec.py
git commit -m "feat(006): frozen f_ablation_spec (40-round policy, 12 arms, 4-model roster, seed)"
```

---

## Task 3: Public `grade_f_attempt` wrapper (so the driver does not import a `_`-name)

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py`
- Test: `tests/runners/test_f_candidate.py`

The driver grades each attempt individually (it cannot use `run_f_candidate`, which drives whole tasks). `f_candidate._grade` already does exactly this but is `_`-private. Add a thin public wrapper; no behavior change.

- [ ] **Step 1: Write the failing test (append to the existing test file)**

```python
# tests/runners/test_f_candidate.py  (append)
def test_grade_f_attempt_wraps_grade_into_a_run_result():
    from agent_eval_lab.runners.f_candidate import grade_f_attempt

    task = _fake_task()
    traj = _traj_with_files({"a.js": "// edited"}, run_index=2)
    result = grade_f_attempt(task, traj, condition_id="prov:m", run_index=2)
    assert result.task_id == "t1"
    assert result.condition_id == "prov:m"
    assert result.run_index == 2
    assert result.trajectory is traj
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_grade_f_attempt_wraps_grade_into_a_run_result -o addopts="" -q`
Expected: FAIL — `ImportError: cannot import name 'grade_f_attempt'`.

- [ ] **Step 3: Add the public wrapper to `f_candidate.py`**

Add immediately after the existing `_grade` function (after line 266):

```python
def grade_f_attempt(
    task: Task, trajectory: Trajectory, *, condition_id: str, run_index: int
) -> RunResult:
    """Public grade for ONE F attempt — the held-out node oracle over the model's
    produced tree, wrapped in a RunResult. Used by the 006 run-f-ablation driver,
    which schedules attempts at (model × arm × rep) granularity and so cannot use
    run_f_candidate (it drives whole tasks). Thin pass-through to _grade; no new
    behavior."""
    return _grade(task, trajectory, condition_id=condition_id, run_index=run_index)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_grade_f_attempt_wraps_grade_into_a_run_result -o addopts="" -q`
Expected: PASS.

- [ ] **Step 5: Run the whole f_candidate suite (no regression)**

Run: `python -m pytest tests/runners/test_f_candidate.py -o addopts="" -q`
Expected: PASS (the `requires_node` integration tests skip without node+repo+store; all unit tests pass).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(006): public grade_f_attempt wrapper over _grade"
```

---

## Task 4: The `run-f-ablation` driver — consumes the order, one artifact per condition, sidecar, `--dry-run`, NO provider call in tests

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (add `_run_f_ablation_command`, imports)
- Test: `tests/cli/test_run_f_ablation.py`

The driver: (1) builds the 12 arm-tasks via `build_f_task_arms`, indexed by `task_id`; (2) realizes the frozen order via `ablation_run_order` with the spec's roster + seed + k; (3) walks the order — for each `RunUnit`, calls the injected/real `run_fn(edit_task, repetition)` (the `make_f_run_fn` interface: `(Task, int) -> Trajectory`), grades it with `grade_f_attempt`, buffers the `RunResult` under its condition; (4) writes one `runs-ablation-{slug}-F.jsonl` per condition (all 12 arms inside) + a `.realized-order.json` sidecar recording the realized API-call order (the order units actually executed). `--dry-run` writes ONLY the sidecar and makes **zero** `run_fn` calls. The `run_fn` is built lazily (only on the real path) so importing/testing never constructs a network client.

The driver signature takes an optional injected `run_fn_factory` so tests pass a fake. Production builds the factory from `make_f_run_fn` per condition.

- [ ] **Step 1: Write the failing tests**

```python
# tests/cli/test_run_f_ablation.py
import json
from pathlib import Path

from agent_eval_lab.cli import _run_f_ablation_command
from agent_eval_lab.experiments.ablation_order import ablation_run_order
from agent_eval_lab.experiments.f_ablation_spec import ABLATION_SEED
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _fake_traj(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        final_state={"files": {"x.js": "// fake edit"}},
        usage=Usage(prompt_tokens=1, completion_tokens=1),
        run_index=run_index,
    )


class _Args:
    """argparse.Namespace stand-in for the driver."""

    def __init__(self, out: Path, *, dry_run: bool):
        self.out = out
        self.evaluator_config = Path("/nonexistent/evaluator.toml")
        self.temperature = 0.0
        self.max_tokens = 16384
        self.dry_run = dry_run


def _make_recording_factory(calls: list):
    """A run_fn_factory that records every (condition, task_id, run_index) and
    NEVER touches the network — proves the driver makes no real provider call."""

    def factory(*, condition_id: str, **_):
        def run_fn(edit_task, run_index: int) -> Trajectory:
            calls.append((condition_id, edit_task.id, run_index))
            return _fake_traj(run_index)

        return run_fn

    return factory


def test_dry_run_writes_order_and_makes_zero_run_fn_calls(tmp_path, monkeypatch):
    # Avoid the real held-out store / candidate-tree git reads on the dry path.
    calls: list = []
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=True),
        http_client=None,
        run_fn_factory=_make_recording_factory(calls),
    )
    assert rc == 0
    assert calls == []  # NO run_fn call on the dry path → NO provider call
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    order = json.loads(sidecars[0].read_text())["realized_order"]
    # 4 arms × 4 models × 3 bases × 5 reps = 240 units recorded, none executed.
    assert len(order) == 240
    assert not list(tmp_path.glob("runs-ablation-*-F.jsonl"))  # no run artifacts


def test_real_path_with_fake_run_fn_writes_one_artifact_per_condition(
    tmp_path, monkeypatch
):
    calls: list = []
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    rc = _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_make_recording_factory(calls),
    )
    assert rc == 0
    # consumed the WHOLE frozen order: 240 attempts, no provider/network call.
    assert len(calls) == 240
    # one artifact per condition (4 conditions), all 12 task-arms inside each.
    artifacts = sorted(tmp_path.glob("runs-ablation-*-F.jsonl"))
    assert len(artifacts) == 4
    for art in artifacts:
        rows = [json.loads(line) for line in art.read_text().splitlines() if line.strip()]
        task_ids = {r["task_id"] for r in rows}
        assert len(task_ids) == 12  # all 12 task-arms in this condition's single file
        assert len(rows) == 12 * 5  # 12 arms × k=5
    # the realized-order sidecar records the executed API-call order.
    sidecars = list(tmp_path.glob("*.realized-order.json"))
    assert len(sidecars) == 1
    realized = json.loads(sidecars[0].read_text())["realized_order"]
    assert len(realized) == 240


def test_realized_order_matches_the_frozen_pure_order(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agent_eval_lab.cli._ablation_arm_tasks", lambda store: _stub_arm_tasks()
    )
    monkeypatch.setattr(
        "agent_eval_lab.cli.build_candidate_tree",
        lambda task, repo: {"x.js": "// base"},
    )
    _run_f_ablation_command(
        _Args(tmp_path, dry_run=False),
        http_client=None,
        run_fn_factory=_make_recording_factory([]),
    )
    sidecar = next(tmp_path.glob("*.realized-order.json"))
    realized = json.loads(sidecar.read_text())["realized_order"]
    expected = ablation_run_order(
        seed=ABLATION_SEED,
        models=(
            "deepseek:deepseek-v4-pro",
            "glm:Pro/zai-org/GLM-5.1",
            "minimax:MiniMax-M3",
            "siliconflow:Qwen/Qwen3.6-35B-A3B",
        ),
        base_tasks=("f1", "f2", "f3"),
        k=5,
    )
    assert [
        (u["model"], u["task_id"], u["repetition"]) for u in realized
    ] == [(u.model, u.task_id, u.repetition) for u in expected]


# --- shared stub: 12 arm-tasks with ids matching the dataset builder ----------
def _stub_arm_tasks():
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import (
        AllOf,
        NodeExecutionSpec,
        Task,
        TaskInput,
        TaskMetadata,
    )

    def _arm(base: str, arm: str) -> Task:
        return Task(
            id=f"f-{base}-{arm}",
            capability="repo_fix",
            input=TaskInput(
                messages=(MessageTurn(role="user", content="fix"),),
                available_tools=("bash",),
            ),
            verification=AllOf(
                specs=(
                    NodeExecutionSpec(
                        held_out_files={"pkg.json": "{}"}, test_paths=("a.test.js",)
                    ),
                )
            ),
            metadata=TaskMetadata(
                split="held_out", version="v", provenance="stub", max_rounds=40
            ),
            initial_state={"repo": "x", "candidate_base_sha": "deadbeef"},
        )

    return {
        f"f-{base}-{arm}": _arm(base, arm)
        for base in ("f1", "f2", "f3")
        for arm in ("bare", "prompt", "feedback", "both")
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/test_run_f_ablation.py -o addopts="" -q`
Expected: FAIL — `ImportError: cannot import name '_run_f_ablation_command'` (and `_ablation_arm_tasks`/`build_candidate_tree` not yet on `cli`).

- [ ] **Step 3: Add the imports + driver to `cli.py`**

Add to the existing `from agent_eval_lab.experiments...` import block (top of cli.py):

```python
from agent_eval_lab.experiments.ablation_order import RunUnit, ablation_run_order
from agent_eval_lab.experiments.f_ablation_spec import (
    ABLATION_SEED,
    build_f_ablation_spec,
)
from agent_eval_lab.runners.f_candidate import (
    build_candidate_tree,
    grade_f_attempt,
    make_edit_task,
    make_f_run_fn,
)
```

Add these functions immediately before `_build_parser` (after `_run_report_m1`, around line 1190):

```python
def _ablation_arm_tasks(store: Path) -> dict[str, Task]:
    """The 12 F task-arms indexed by task_id (the arm rides task_id, §B.2)."""
    from agent_eval_lab.datasets.f_tasks import build_f_task_arms

    return {t.id: t for t in build_f_task_arms(evaluator_store=store)}


def _default_run_fn_factory(
    *, http_client: httpx.Client | None, temperature: float, max_tokens: int
):
    """Production factory: per condition_id, build the REAL make_f_run_fn driver.
    Called ONLY on a non-dry user invocation — this is the sole provider-call path
    (V arms route through the 005 sandbox on macOS via make_f_run_fn). Tests inject
    a fake factory instead, so no test/CI path ever reaches a network client."""

    def factory(*, condition_id: str, safety_cap: int):
        provider = condition_id.split(":", 1)[0]
        config = PROVIDERS[provider]
        model = condition_id.split(":", 1)[1]
        config = replace(config, model_id=model)
        client = http_client or httpx.Client(
            timeout=120.0, trust_env=False, proxy=resolve_proxy(config, os.environ)
        )
        return make_f_run_fn(
            config=config,
            http_client=client,
            temperature=temperature,
            max_tokens=max_tokens,
            condition_id=condition_id,
            safety_cap=safety_cap,
            max_rounds=40,  # the frozen uniform ablation cap (§B.1)
        )

    return factory


def _run_f_ablation_command(  # noqa: C901
    args: argparse.Namespace,
    http_client: httpx.Client | None,
    *,
    run_fn_factory=None,
) -> int:
    """EDGE: orchestrate the F-set ablation in the FROZEN seeded ablation_run_order
    across (model × task-arm × rep). The arm rides each run's task_id (§B.2). Writes
    one artifact per condition (runs-ablation-{slug}-F.jsonl, all 12 task-arms
    inside) + a realized-order sidecar (the API-call order controls drift, not the
    on-disk record order — §10.7).

    Provider calls happen ONLY when the user invokes this WITHOUT --dry-run and with
    no injected run_fn_factory. --dry-run writes the realized order and makes ZERO
    run_fn calls (a network-free preview + the unit-test seam)."""
    spec = build_f_ablation_spec(dataset_snapshot_hash="", pricing_snapshot_hash="")
    models = tuple(c.condition_id for c in spec.conditions)
    base_tasks = ("f1", "f2", "f3")
    order = ablation_run_order(
        seed=ABLATION_SEED, models=models, base_tasks=base_tasks, k=spec.k
    )

    args.out.mkdir(parents=True, exist_ok=True)
    realized: list[RunUnit] = []

    if args.dry_run:
        # Preview ONLY: record the realized order, make NO run_fn call (no network).
        _write_realized_order(args.out, order)
        print(args.out / "f-ablation.realized-order.json")
        return 0

    cfg = load_evaluator_config(args.evaluator_config)
    store = Path(cfg.store.path) / "web-dossier-golden"
    f_repo = Path.home() / "Documents/Repository/web-dossier"
    arm_tasks = _ablation_arm_tasks(store)
    factory = run_fn_factory or _default_run_fn_factory(
        http_client=http_client,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    run_fns: dict[str, object] = {}
    buffers: dict[str, list[RunResult]] = {cond: [] for cond in models}
    for unit in order:
        run_fn = run_fns.get(unit.model)
        if run_fn is None:
            run_fn = factory(condition_id=unit.model, safety_cap=cfg.runner.safety_cap)
            run_fns[unit.model] = run_fn
        task = arm_tasks[unit.task_id]
        base_tree = build_candidate_tree(task, repo=f_repo)
        edit_task = make_edit_task(task, base_tree=base_tree)
        traj = run_fn(edit_task, unit.repetition)
        buffers[unit.model].append(
            grade_f_attempt(
                task, traj, condition_id=unit.model, run_index=unit.repetition
            )
        )
        realized.append(unit)

    for cond, runs in buffers.items():
        path = args.out / f"runs-ablation-{_slug(cond)}-F.jsonl"
        with path.open("w") as fh:
            _append_runs(fh, runs)
    _write_realized_order(args.out, tuple(realized))
    print(args.out)
    return 0


def _write_realized_order(out: Path, order: Sequence[RunUnit]) -> None:
    """Persist the realized execution / API-call order for audit (§10.7). Pure
    projection of RunUnits to plain dicts; the on-disk record order in the JSONL is
    NOT this — this sidecar is the authoritative drift-control record."""
    payload = {
        "seed": ABLATION_SEED,
        "realized_order": [
            {
                "model": u.model,
                "task_id": u.task_id,
                "base_task": u.base_task,
                "arm": u.arm,
                "repetition": u.repetition,
            }
            for u in order
        ],
    }
    (out / "f-ablation.realized-order.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
```

Note: add `Task` to the existing `from agent_eval_lab.tasks.schema import ...` line in cli.py (it currently imports only `LlmJudgeSpec`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/cli/test_run_f_ablation.py -o addopts="" -q`
Expected: PASS (3 passed) — including `test_dry_run_...` asserting `calls == []` (zero `run_fn` calls) and the real-path test asserting 240 fake calls, 4 artifacts, the sidecar, and NO network.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/cli/test_run_f_ablation.py
git commit -m "feat(006): run-f-ablation driver (frozen order, one artifact/condition, sidecar, --dry-run)"
```

---

## Task 5: Wire `run-f-ablation` into the CLI parser + dispatch

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (`_build_parser` + `main` dispatch)
- Test: `tests/cli/test_run_f_ablation.py` (append a parse-args wiring test)

- [ ] **Step 1: Write the failing test (append)**

```python
# tests/cli/test_run_f_ablation.py  (append)
def test_parser_exposes_run_f_ablation_with_dry_run():
    from agent_eval_lab.cli import _build_parser

    parser = _build_parser()
    args = parser.parse_args(
        [
            "run-f-ablation",
            "--evaluator-config",
            "evaluator.toml",
            "--out",
            "reports",
            "--dry-run",
        ]
    )
    assert args.command == "run-f-ablation"
    assert args.dry_run is True
    assert args.max_tokens == 16384  # F default


def test_dispatch_routes_run_f_ablation(tmp_path, monkeypatch):
    import agent_eval_lab.cli as cli

    seen = {}

    def _spy(args, http_client):
        seen["called"] = True
        return 0

    monkeypatch.setattr(cli, "_run_f_ablation_command", _spy)
    rc = cli.main(
        ["run-f-ablation", "--evaluator-config", "x.toml", "--dry-run"],
        http_client=None,
    )
    assert rc == 0 and seen["called"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/cli/test_run_f_ablation.py::test_parser_exposes_run_f_ablation_with_dry_run tests/cli/test_run_f_ablation.py::test_dispatch_routes_run_f_ablation -o addopts="" -q`
Expected: FAIL — `argument command: invalid choice: 'run-f-ablation'`.

- [ ] **Step 3: Add the subparser (in `_build_parser`, after the `run-f` block ~line 1343)**

```python
    rfa = subparsers.add_parser(
        "run-f-ablation",
        help="orchestrate the F-set 2×2 ablation in the frozen seeded order "
        "(one artifact per condition + realized-order sidecar). --dry-run previews "
        "the order with NO provider calls.",
    )
    rfa.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rfa.add_argument("--out", type=Path, default=Path("reports"))
    rfa.add_argument("--temperature", type=float, default=0.0)
    rfa.add_argument("--max-tokens", type=int, default=16384)
    rfa.add_argument(
        "--dry-run",
        action="store_true",
        help="write the realized run order and exit WITHOUT any provider call "
        "(network-free preview / audit).",
    )
```

- [ ] **Step 4: Add the dispatch (in `main`, before the trailing `return _run_baseline_command(...)`):**

```python
    if args.command == "run-f-ablation":
        return _run_f_ablation_command(args, http_client)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/cli/test_run_f_ablation.py -o addopts="" -q`
Expected: PASS (5 passed).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/cli.py tests/cli/test_run_f_ablation.py
git commit -m "feat(006): wire run-f-ablation subcommand + dispatch"
```

---

## Task 6: Report compatibility check — `pass_pow_k` groups by `task_id` (confirm, change nothing)

**Files:**
- Test: `tests/cli/test_run_f_ablation.py` (append — a confirmation test; no source change)

§B.2 / the spec's "Report compatibility" criterion: confirm (do not change) that per-arm pass^k separates for free because `pass_pow_k` keys on `task_id`. The arm rides `task_id`, so a one-artifact-per-condition file with 12 task-arms × 5 reps yields 12 per-task reliabilities — the 4 arms partition into 4 sets of 3.

- [ ] **Step 1: Write the confirmation test (append)**

```python
# tests/cli/test_run_f_ablation.py  (append)
def test_per_arm_pass_pow_k_separates_by_task_id_no_report_change():
    """The arm rides task_id, so pass_pow_k (keyed on task_id) yields one
    reliability per task-arm — 12 here, partitioning into 4 arms × 3 bases. This
    asserts the EXISTING reliability.pass_pow_k contract; it changes nothing."""
    from agent_eval_lab.metrics.reliability import pass_pow_k
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    def _run(task_id: str, passed: bool, idx: int) -> RunResult:
        return RunResult(
            task_id=task_id,
            condition_id="prov:m",
            run_index=idx,
            trajectory=Trajectory(
                turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0),
                run_index=idx,
            ),
            grade=GradeResult(passed=passed, score=1.0 if passed else 0.0),
        )

    # f1: bare fails, prompt/feedback/both pass (k=2 each, all-pass = reliable).
    runs = []
    for arm, ok in (("bare", False), ("prompt", True), ("feedback", True), ("both", True)):
        for i in range(2):
            runs.append(_run(f"f-f1-{arm}", ok, i))
    # pass_pow_k over the 4 task-arms: 3 of 4 are all-pass → 0.75.
    assert pass_pow_k(runs) == 0.75
    # grouping is by task_id (the arm) — 4 distinct task-arms seen.
    assert len({r.task_id for r in runs}) == 4
```

- [ ] **Step 2: Run test to verify it passes immediately (no source change needed)**

Run: `python -m pytest tests/cli/test_run_f_ablation.py::test_per_arm_pass_pow_k_separates_by_task_id_no_report_change -o addopts="" -q`
Expected: PASS — confirms the existing contract; if it FAILED it would mean a report-side change is required (it is not).

- [ ] **Step 3: Commit**

```bash
git add tests/cli/test_run_f_ablation.py
git commit -m "test(006): confirm per-arm pass^k separates by task_id (no report change)"
```

---

## Task 7: Full-suite gate + lint + the two demonstration commands

**Files:** none (verification only).

- [ ] **Step 1: Run the whole test suite**

Run: `python -m pytest -o addopts="" -q`
Expected: PASS — all tests green; `requires_node`/macOS-gated integration tests SKIP (no node/repo/store/Darwin in CI). No test makes a network call.

- [ ] **Step 2: Lint (CI runs both, whole-repo)**

Run: `ruff check . && ruff format --check .`
Expected: both report no changes / all checks passed. (If `ruff format --check .` flags files, run `ruff format .`, re-run the suite, and amend the relevant commit.)

- [ ] **Step 3: Demonstrate `run-f-ablation --dry-run` realizes the order WITHOUT any provider call**

Run:
```bash
python -m agent_eval_lab.cli run-f-ablation \
  --evaluator-config evaluator.toml \
  --out /tmp/abl-dryrun --dry-run
```
Expected stdout: `/tmp/abl-dryrun/f-ablation.realized-order.json`. Then:
```bash
python -c "import json; d=json.load(open('/tmp/abl-dryrun/f-ablation.realized-order.json')); print(len(d['realized_order']), d['seed'])"
```
Expected: `240 20260615`. And `ls /tmp/abl-dryrun/runs-ablation-*-F.jsonl` → no such files (the dry path writes NO run artifacts and made NO provider call — the evaluator config is never even read on the dry path).

- [ ] **Step 4: Demonstrate the frozen `f_ablation_spec` (spec_hash) — separate from m1**

Run:
```bash
python -c "
import json
from agent_eval_lab.experiments.f_ablation_spec import build_f_ablation_spec, ablation_policy, freeze_ablation_policy
from agent_eval_lab.experiments.spec_hash import freeze_spec, canonical_json
from agent_eval_lab.cli import _spec_to_dict
spec = freeze_spec(build_f_ablation_spec(dataset_snapshot_hash='ds', pricing_snapshot_hash='pr'))
json.dump(_spec_to_dict(spec), open('/tmp/f-ablation-spec.draft.json','w'), indent=2, sort_keys=True)
print('spec_hash', spec.spec_hash)
print('policy_hash', freeze_ablation_policy(ablation_policy()).policy_hash)
"
python -m agent_eval_lab.cli freeze-spec \
  --spec /tmp/f-ablation-spec.draft.json \
  --out /tmp/f-ablation-spec.frozen.json
```
Expected: the first command prints a 64-hex `spec_hash` and a 64-hex `policy_hash`; `freeze-spec` prints the SAME `spec_hash` (idempotent — the draft is already frozen) and writes `/tmp/f-ablation-spec.frozen.json`. This is the existing `freeze_spec` path — m1's committed frozen specs are untouched.

- [ ] **Step 5: Confirm m1's committed frozen spec still verifies (final regression)**

Run:
```bash
python -c "
import json
from agent_eval_lab.cli import _spec_from_dict
from agent_eval_lab.experiments.spec_hash import verify_spec_hash
d = json.load(open('reports/agentic-v1/M1-spec.frozen.json'))
print('M1 verify_spec_hash:', verify_spec_hash(_spec_from_dict(d)))
"
```
Expected: `M1 verify_spec_hash: True`.

- [ ] **Step 6: Commit any lint fixes (only if Step 2 produced changes)**

```bash
git add -u src/agent_eval_lab tests
git commit -m "chore(006): ruff format"
```

---

## Self-Review

### Spec acceptance criteria → task mapping

**Pure `ablation_run_order` (§B.7 / §11.9):**
- Pure `ablation_run_order(seed, models, base_tasks, k)` returning `(model, task_arm, repetition)` units → **Task 1** (`RunUnit` carries `model`/`base_task`/`arm`/`repetition`; `task_id` property = `f-{base}-{arm}`).
- Interleaves all four arms within each `(model, base-task, rep)` block → **Task 1 Step 3** (`rng.shuffle(block)` per block) + asserted in `test_arms_interleaved_within_each_block_not_arm_grouped`.
- Deterministic / different-seed-differs / no wall-clock → **Task 1** `test_same_seed_is_identical`, `test_different_seed_differs`, `test_no_wall_clock_dependence_two_calls_equal` (single `random.Random(seed)`).
- Total coverage, no dup (240 at k=5) → **Task 1** `test_total_coverage_each_unit_exactly_once_at_k5` (asserts `4×models×bases×k`, Counter all == 1).

**`run-f-ablation` CLI driver (§B.7 / §G6):**
- New subcommand executing the frozen order across (model × task-arm × rep), arm in `task_id`, using `build_f_task_arms`/`build_candidate_tree`/`make_f_run_fn` → **Task 4** (driver) + **Task 5** (wiring). Uses all three seams.
- One artifact per condition (`runs-ablation-{slug}-F.jsonl`, all 12 arms inside), not per-arm → **Task 4** (`buffers[cond]` → one file/condition) + `test_real_path_..._one_artifact_per_condition` (4 files, 12 task_ids each).
- Realized-order sidecar → **Task 4** (`_write_realized_order`) + `test_real_path...`, `test_realized_order_matches_the_frozen_pure_order`, `test_dry_run...`.
- No paid execution; tests inject a fake run_fn; optional `--dry-run` → **Task 4/5** (`run_fn_factory` injection; `--dry-run` makes zero `run_fn` calls — `test_dry_run_writes_order_and_makes_zero_run_fn_calls` asserts `calls == []`).

**Frozen `experiments/f_ablation_spec.py` (§B.1 / §B.6 / §11.9):**
- Separate spec recording 40-round policy, 12 task-arms, 4-model roster, seed → **Task 2** (`AblationPolicy` + `build_f_ablation_spec`).
- Frozen via `freeze_spec` path / recorded hash → **Task 2** (`ExperimentSpec` via `freeze_spec`; `AblationPolicy` via `freeze_ablation_policy` using the same `canonical_json`+sha256) + `test_spec_freezes_and_verifies_independently_of_m1`, `test_freeze_ablation_policy...`.
- Does NOT touch frozen M1 specs; `verify_spec_hash` for M1 still passes; no schema change → **Task 2** `test_building_the_ablation_spec_does_not_touch_m1` + **Task 7 Step 5** (verifies committed `M1-spec.frozen.json`). No `ConditionDef`/`ExperimentSpec` field added; `condition_id` stays `provider:model`.

**Report compatibility (§B.2):**
- Confirm (don't change) `pass_pow_k` groups by `task_id` → **Task 6** (`test_per_arm_pass_pow_k_separates_by_task_id_no_report_change`; no source change).

### Placeholder scan
No TBD/TODO/"add error handling"/"similar to Task N". Every code step shows complete code; every command shows expected output. The driver `# noqa: C901` mirrors the existing `_run_check_env`/`_run_dset_command` complexity-waiver convention in cli.py.

### Type consistency
- `RunUnit` fields (`model`, `base_task`, `arm`, `repetition`, `.task_id`) used identically in Tasks 1, 4, and `_write_realized_order`.
- `run_fn_factory(*, condition_id, safety_cap)` → returns `run_fn(edit_task, run_index) -> Trajectory` — matches `make_f_run_fn`'s returned `(Task, int) -> Trajectory` (f_candidate.py:214) and the fake factories in Task 4 tests.
- `grade_f_attempt(task, trajectory, *, condition_id, run_index)` (Task 3) signature == its call site in Task 4.
- `build_f_ablation_spec(*, dataset_snapshot_hash, pricing_snapshot_hash)` == `build_m1_spec` shape; consumed by `freeze_spec` unchanged.
- `AblationPolicy.policy_hash` blanked-then-hashed mirrors `compute_spec_hash`'s blank-`spec_hash` pattern exactly.

### NO paid execution path runs in tests or CI — explicit statement
- The **only** code that constructs a network `httpx.Client` and a real model driver is `_default_run_fn_factory` (Task 4), reached **only** on a non-`--dry-run` user invocation with **no** injected `run_fn_factory`.
- Every driver test injects a fake `run_fn_factory` (records calls, returns a canned `Trajectory`) — **no** test ever calls `_default_run_fn_factory`, so no `httpx.Client` is built and no provider is contacted.
- The `--dry-run` test asserts `calls == []` — the dry path does not even read the evaluator config or build candidate trees; it makes **zero** `run_fn` calls.
- V arms route through the 005 macOS sandbox **only** inside `make_f_run_fn` (off the test path entirely); CI is non-Darwin and never reaches it.
- This item builds orchestration and freezes a spec; the pilot (≈24) and full 240-attempt paid run remain **user-triggered later** via this driver (spec Non-goals; MASTER-SPEC hard boundary). The plan adds no auto-run anywhere.
