# Item 003 — Arm-as-task + Factor P — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Express the F harness-factor ablation's four arms as four distinct `task_id`s per base task (12 task-arms = 3 bases × 4 arms), add the attributable Factor-P prompt block, and make `run_uid` task-scoped — riding the data model the codebase already has (`task_id`), with **no** new record/spec fields.

**Architecture:** Mirror the M2 arm-as-task pattern from `b_tasks.py` (`b-b1-noskill`/`b-b1-skill`): one shared held-out `VerificationSpec` and one shared base tree across arms; arms differ only in Factor P (a system-prompt block) and Factor V (the declared tool surface). The arm identity rides `task_id` (`f-f1-bare`/`-prompt`/`-feedback`/`-both`). Because `make_edit_task` (f_candidate.py) **rebuilds the system message from `_EDIT_SYSTEM` at run time** — discarding any dataset-level system turn — Factor P cannot ride the dataset task's `messages` the way B does; instead each arm carries a small discriminator on `initial_state` (`factor_p: bool`, `factor_v: bool`) that `make_edit_task` reads to append the P block and that the builder uses to set `available_tools`. `run_uid` becomes `{condition_id}__{task_id}__{run_index:04d}`, read from the edit task's preserved `id`.

**Tech Stack:** Python 3.12, dataclasses (`Task`/`TaskInput`/`TaskMetadata`, all `frozen=True`), pytest, ruff. Pure FP house style (CLAUDE.md): immutable builders returning new `Task`s, no shared mutable state.

---

## Key design decisions (locked before coding)

### D1 — Factor P injection point: `make_edit_task`, gated by an `initial_state` flag
`make_edit_task` (`src/agent_eval_lab/runners/f_candidate.py:113`) rebuilds the system turn from `_EDIT_SYSTEM.format(...)`, **discarding** the dataset task's own system message. So the B pattern (append P to `messages` in the dataset builder) would be silently overwritten for F. Therefore:
- The Factor-P block is a **named isolated module constant** `_FACTOR_P_BLOCK` in `f_candidate.py` (alongside `_EDIT_SYSTEM`, so the run-time system prompt is single-sourced and the block is attributable/diff-able).
- `make_edit_task` reads a boolean `factor_p` from the task's `initial_state` (default `False`) and, when true, appends `"\n\n" + _FACTOR_P_BLOCK` to the formatted `_EDIT_SYSTEM`.
- The dataset builder (`build_f_task_arms`) sets `initial_state["factor_p"]` per arm. `initial_state` is a plain `Mapping` already round-tripped through `final_state`/serialize seams and is **not** part of the hashed `ExperimentSpec` — so this adds **no** schema field, **no** `arm_id`, and does not touch `verify_spec_hash`.

This satisfies the spec's "discrete, attributable block appended to `_EDIT_SYSTEM`, applied to prompt/both only, a named isolated constant" (§B.3) while surviving `make_edit_task`.

### D2 — Factor V tool surface representation (the spec's required plan-phase judgment call)
**Decision: declare the V `run_tests` tool name in each V arm's `available_tools` (and on `initial_state["factor_v"]=True`), but bind NO executor in 003.** The `feedback`/`both` arms list `run_tests` in `available_tools` so the arm's tool *surface* (its identity) is established now; the live sandboxed executor, the V-specific node-accurate `ToolDef`, and the world-binding that makes `run_tests` actually run authored tests are **item 005** (`make_f_run_fn` keeps `executor=None` for every arm in 003).

**Trade-off considered.** The alternative — defer the V tool surface entirely to 005 — would make `feedback`/`both` byte-identical to `bare`/`prompt` in 003, erasing the arm distinction this item is meant to establish, and would force 005 to re-edit the builder. Declaring the name now keeps the four arms genuinely distinct (the 2×2 is real in the task records) at the cost of a tool name that is not yet executable. We accept that cost because: (a) `make_f_run_fn` runs F through `CODE_WORLD_TOOLS` and only dispatches tools the model calls; with `executor=None` the loop never wires `run_tests` to a runner, and (b) 003 ships **no paid execution** — V arms are constructed and unit-tested offline only. To make the not-yet-wired surface explicit rather than silently broken, 003 adds a guard in `make_f_run_fn` that **raises** if a V arm (`factor_v=True`) is handed to the live driver, so no one accidentally runs a V arm against a provider before 005 wires the executor. `bare`/`prompt` (`factor_v=False`) stay fully runnable today.

This satisfies §B.2 ("Factor V rides the task's `available_tools`") and the Non-goal boundary ("V arms establish arm identity + tool surface; they must NOT have a live V loop ... must not fabricate a working V executor"). We do **not** define the V-specific `run_tests` `ToolDef` here (§10.8 / Non-goal: that is 005) — only the tool *name* string in `available_tools`.

### D3 — `run_uid` task-scoping reads the edit task's preserved id
`run_f_candidate` calls `run_fn(edit_task, i)`; `edit_task = make_edit_task(task, ...)` preserves `task.id` via `replace(task, ...)`. So `make_f_run_fn`'s closure already receives the per-arm task and can build `run_uid=f"{condition_id}__{edit_task.id}__{run_index:04d}"`. No signature change to `run_fn`.

### D4 — Carry-forward (002 review): per-task F `max_rounds` override path reachable
The spec's Constraints note (lines 99-104) asks only that the per-task override path be *reachable* now; the 40-round policy value is frozen later in 006's `f_ablation_spec`. `resolve_max_rounds` (`round_budget.py`) already honors `task.metadata.max_rounds` over the domain default. 003 therefore sets `metadata.max_rounds=40` on each F task-arm so the override path is exercised, and adds a test asserting `resolve_max_rounds(domain="F", task=arm)` returns 40. No new wiring; full driver wiring stays in 006.

---

## File structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_eval_lab/datasets/f_tasks.py` | Build the 12 F task-arms (3 bases × 4 arms) sharing each base's verification + tree-driving `initial_state`, differing only by `factor_p`/`factor_v` flags and `available_tools`. | Modify |
| `src/agent_eval_lab/runners/f_candidate.py` | Add `_FACTOR_P_BLOCK`; make `make_edit_task` append it when `initial_state["factor_p"]`; task-scope `run_uid`; guard live V arms in `make_f_run_fn`. | Modify |
| `tests/datasets/test_f_tasks.py` | Cover: 12 arm ids, shared verification + byte-identical tree, P/V flag → arm mapping, max_rounds=40 override reachable. | Modify |
| `tests/runners/test_f_candidate.py` | Cover: P block present on prompt/both only; V tool name on feedback/both only; run_uid task-scoped + collision-free; V-arm live-run guard. | Modify |
| `tests/experiments/test_m1_spec.py` | Confirm `verify_spec_hash` still passes (unchanged file; we run its existing test as a regression gate — no edit). | Verify only |

No new files. No `arm_id`/`ArmDef`/`tool_set_hash`/`ConditionDef`/`ExperimentSpec`/serialize changes.

---

## Constants used across tasks (defined once, referenced by id)

The exact arm name set (used in every task that enumerates arms):

```
f-f1-bare  f-f1-prompt  f-f1-feedback  f-f1-both
f-f2-bare  f-f2-prompt  f-f2-feedback  f-f2-both
f-f3-bare  f-f3-prompt  f-f3-feedback  f-f3-both
```

Arm → factor mapping (the 2×2):

| arm suffix | `factor_p` | `factor_v` | `available_tools` |
|---|---|---|---|
| `-bare` | `False` | `False` | `("bash",)` |
| `-prompt` | `True` | `False` | `("bash",)` |
| `-feedback` | `False` | `True` | `("bash", "run_tests")` |
| `-both` | `True` | `True` | `("bash", "run_tests")` |

> Note on `available_tools` at the **dataset** level: the F dataset task carries the prose `bash` tool (matching the un-armed `f_tasks.py` today, line 72), and `make_edit_task` swaps it for `F_EDIT_TOOL_NAMES` at run time. For V arms we additionally append the `"run_tests"` name so the arm's intended surface is recorded on the dataset task; `make_edit_task` will preserve that V name (see Task 4). The `bash` token is the dataset-level placeholder; the run-time edit tools are `F_EDIT_TOOL_NAMES` (+ `run_tests` for V arms).

The verbatim Factor-P block (vocabulary uses "visible tests", per §11.4):

```
Before editing, gather context. Read the full body of any method that a call or
assertion you touch depends on — do not assume its contract from its name. Before
adding a method, read the sibling methods in the same file so your addition matches
their shape and conventions. Read the local conventions for this layer (its
README, config, or nearest CLAUDE.md) before you write. Read the entire target
file and the full set of visible tests that exercise it before your first edit.
Change only what the task requires; leave every other file and layer untouched.
```

---

## Task 1: Build the 12 F task-arms (arm-as-task structure)

**Files:**
- Modify: `src/agent_eval_lab/datasets/f_tasks.py`
- Test: `tests/datasets/test_f_tasks.py`

- [ ] **Step 1: Write the failing test for 12 arm ids**

Add to `tests/datasets/test_f_tasks.py` (the file's `_STORE` / `requires_store` fixtures already exist at the top):

```python
def _arm_ids() -> list[str]:
    return [
        f"f-{base}-{arm}"
        for base in ("f1", "f2", "f3")
        for arm in ("bare", "prompt", "feedback", "both")
    ]


@requires_store
def test_build_f_task_arms_returns_twelve_arms_with_suffixed_ids() -> None:
    arms = build_f_task_arms(evaluator_store=_STORE)
    assert sorted(t.id for t in arms) == sorted(_arm_ids())
    assert len(arms) == 12
    for t in arms:
        assert t.capability == "repo_fix"
        assert t.metadata.split == "held_out"
        assert t.initial_state is not None
        assert t.initial_state["candidate_base_sha"].startswith("5b0c13a6")
```

Add the import at the top of the test file (next to the existing `build_f_tasks` import):

```python
from agent_eval_lab.datasets.f_tasks import build_f_task_arms, build_f_tasks
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/datasets/test_f_tasks.py -o addopts="" -q`
Expected: ImportError / `cannot import name 'build_f_task_arms'` (collection error) — confirms the builder does not yet exist.

- [ ] **Step 3: Add the four-arm fan-out to `f_tasks.py`**

In `src/agent_eval_lab/datasets/f_tasks.py`, replace the `_task` helper and `build_f_tasks` function (lines 61-108) with a base-task helper plus a per-base arm fan-out. Keep `build_f_tasks` (the un-armed 3-task builder) intact — it is still used by production `m1_spec` F and the existing tests — and add `build_f_task_arms` beside it.

Replace the existing `_task(...)` definition (lines 61-85) with:

```python
# Arm -> (factor_p, factor_v) — the 2x2 (spec item 003 §B.1).
_ARM_FACTORS: dict[str, tuple[bool, bool]] = {
    "bare": (False, False),
    "prompt": (True, False),
    "feedback": (False, True),
    "both": (True, True),
}

# Factor V's tool name. The executor that binds it is item 005; here it only
# records the V arms' tool SURFACE (their identity). bare/prompt never see it.
_V_TOOL = "run_tests"

# The F-ablation runs every arm under a uniform 40-round cap (§B.1); production F
# stays 20. The value is FROZEN in item 006's f_ablation_spec — here it only makes
# the per-task max_rounds override path reachable (resolve_max_rounds honors it).
_ABLATION_MAX_ROUNDS = 40


def _task(
    *, task_id: str, user: str, verification, target_paths: tuple[str, ...]
) -> Task:
    return Task(
        id=task_id,
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content=_SYSTEM),
                MessageTurn(role="user", content=user),
            ),
            available_tools=("bash",),
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="f-domain-v1",
            provenance="web-dossier PR #23483 (pre-fix 5b0c13a6)",
        ),
        initial_state={
            "repo": "web-dossier",
            "candidate_base_sha": _CANDIDATE_BASE_SHA,
            "target_paths": target_paths,
        },
    )


def _arm(
    *, base: str, arm: str, user: str, verification, target_paths: tuple[str, ...]
) -> Task:
    """One arm-task of a base F task: same held-out verification + same
    tree-driving initial_state as its three siblings, differing only in the
    factor_p/factor_v flags (read by make_edit_task) and available_tools."""
    factor_p, factor_v = _ARM_FACTORS[arm]
    tools = ("bash", _V_TOOL) if factor_v else ("bash",)
    return Task(
        id=f"f-{base}-{arm}",
        capability="repo_fix",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content=_SYSTEM),
                MessageTurn(role="user", content=user),
            ),
            available_tools=tools,
        ),
        verification=verification,
        metadata=TaskMetadata(
            split="held_out",
            version="f-domain-v1",
            provenance="web-dossier PR #23483 (pre-fix 5b0c13a6)",
            max_rounds=_ABLATION_MAX_ROUNDS,
        ),
        initial_state={
            "repo": "web-dossier",
            "candidate_base_sha": _CANDIDATE_BASE_SHA,
            "target_paths": target_paths,
            "factor_p": factor_p,
            "factor_v": factor_v,
        },
    )
```

> Leave the existing `build_f_tasks` (lines 88-108) **unchanged**.

- [ ] **Step 4: Add `build_f_task_arms` below `build_f_tasks`**

Append to `src/agent_eval_lab/datasets/f_tasks.py` (after `build_f_tasks`):

```python
def build_f_task_arms(*, evaluator_store: Path) -> tuple[Task, ...]:
    """The 12 F task-arms (3 base tasks x 4 arms) for the harness-factor ablation
    (item 003 §B.1). Each base's four arms share that base's held-out
    VerificationSpec and tree-driving initial_state byte-for-byte; they differ
    ONLY in Factor P (a system-prompt block, gated by initial_state['factor_p'])
    and Factor V (the declared tool surface, initial_state['factor_v'] +
    available_tools). The arm IS the task_id — no arm_id, no spec change."""
    bases = (
        ("f1", _F1_USER, build_f1_verification(evaluator_store), (F1_SPEC_REL, F1_PAGE_REL)),
        ("f2", _F2_USER, build_f2_verification(evaluator_store), (F2_CONF_REL,)),
        ("f3", _F3_USER, build_f3_verification(evaluator_store), (F3_SOURCE_REL,)),
    )
    return tuple(
        _arm(base=base, arm=arm, user=user, verification=verification, target_paths=paths)
        for base, user, verification, paths in bases
        for arm in ("bare", "prompt", "feedback", "both")
    )
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest tests/datasets/test_f_tasks.py::test_build_f_task_arms_returns_twelve_arms_with_suffixed_ids -o addopts="" -q`
Expected: `1 passed` (requires the local golden store; if the store is absent the test SKIPS — see Step 6).

- [ ] **Step 6: If the test SKIPPED (no local golden store), confirm it skips for the right reason**

Run: `python -m pytest tests/datasets/test_f_tasks.py -o addopts="" -rs -q`
Expected: every test in the file reports `s` (skipped) with reason `local web-dossier golden store required`, and **0 failed / 0 errors**. A collection ImportError here is a real failure (the builder is missing) — distinguish that from a clean skip.

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/datasets/f_tasks.py tests/datasets/test_f_tasks.py
git commit -m "feat(003): build 12 F task-arms (arm-as-task)"
```

---

## Task 2: Arms share byte-identical verification + tree-driving initial_state

**Files:**
- Test: `tests/datasets/test_f_tasks.py`
- (No source change — this asserts the invariant Task 1 produced.)

- [ ] **Step 1: Write the failing test**

Add to `tests/datasets/test_f_tasks.py`:

```python
@requires_store
def test_four_arms_of_a_base_share_verification_and_tree_state() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for base, paths_key in (("f1", None), ("f2", None), ("f3", None)):
        suffixes = ("bare", "prompt", "feedback", "both")
        group = [arms[f"f-{base}-{s}"] for s in suffixes]
        ref = group[0]
        for t in group[1:]:
            # SAME held-out oracle object (identity, not just equality)
            assert t.verification == ref.verification
            # byte-identical tree-driving state: same repo, base SHA, target paths
            assert t.initial_state["repo"] == ref.initial_state["repo"]
            assert (
                t.initial_state["candidate_base_sha"]
                == ref.initial_state["candidate_base_sha"]
            )
            assert (
                t.initial_state["target_paths"] == ref.initial_state["target_paths"]
            )


@requires_store
def test_arms_differ_only_in_factor_flags_and_tools() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    # 2x2 factor mapping
    assert arms["f-f1-bare"].initial_state["factor_p"] is False
    assert arms["f-f1-bare"].initial_state["factor_v"] is False
    assert arms["f-f1-prompt"].initial_state["factor_p"] is True
    assert arms["f-f1-prompt"].initial_state["factor_v"] is False
    assert arms["f-f1-feedback"].initial_state["factor_p"] is False
    assert arms["f-f1-feedback"].initial_state["factor_v"] is True
    assert arms["f-f1-both"].initial_state["factor_p"] is True
    assert arms["f-f1-both"].initial_state["factor_v"] is True
    # V arms declare the run_tests tool surface; non-V arms do not
    assert "run_tests" in arms["f-f1-feedback"].input.available_tools
    assert "run_tests" in arms["f-f1-both"].input.available_tools
    assert "run_tests" not in arms["f-f1-bare"].input.available_tools
    assert "run_tests" not in arms["f-f1-prompt"].input.available_tools
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/datasets/test_f_tasks.py::test_four_arms_of_a_base_share_verification_and_tree_state tests/datasets/test_f_tasks.py::test_arms_differ_only_in_factor_flags_and_tools -o addopts="" -q`
Expected: `2 passed` (or `2 skipped` if no local store — re-run Step 6 of Task 1's distinguishing check). These pass against Task 1's output with no source change — they lock the invariant.

- [ ] **Step 3: Add the max_rounds-override-reachable test**

Add to `tests/datasets/test_f_tasks.py`:

```python
@requires_store
def test_each_arm_carries_the_40_round_ablation_override() -> None:
    from agent_eval_lab.runners.round_budget import resolve_max_rounds

    for t in build_f_task_arms(evaluator_store=_STORE):
        assert t.metadata.max_rounds == 40
        # the per-task override path is reachable: it WINS over the F default (20)
        assert resolve_max_rounds(domain="F", task=t) == 40
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/datasets/test_f_tasks.py::test_each_arm_carries_the_40_round_ablation_override -o addopts="" -q`
Expected: `1 passed` (or skipped without the store).

- [ ] **Step 5: Commit**

```bash
git add tests/datasets/test_f_tasks.py
git commit -m "test(003): arms share verification+tree; differ only by P/V flags"
```

---

## Task 3: Factor-P block, appended in `make_edit_task` for prompt/both only

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py:51-59` (add `_FACTOR_P_BLOCK`) and `:113-129` (`make_edit_task`)
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/runners/test_f_candidate.py` (its imports already include `make_edit_task`):

```python
def _flagged_task(*, factor_p: bool, factor_v: bool) -> Task:
    base = _fake_task()
    state = {**base.initial_state, "factor_p": factor_p, "factor_v": factor_v}
    if factor_v:
        return replace(
            base,
            input=TaskInput(
                messages=base.input.messages,
                available_tools=("bash", "run_tests"),
            ),
            initial_state=state,
        )
    return replace(base, initial_state=state)


def test_factor_p_block_present_only_on_prompt_and_both_arms() -> None:
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    def sys_of(task: Task) -> str:
        edit = make_edit_task(task, base_tree={"a.js": "x\n"})
        return next(m for m in edit.input.messages if m.role == "system").content

    # P arms: block present
    assert _FACTOR_P_BLOCK in sys_of(_flagged_task(factor_p=True, factor_v=False))
    assert _FACTOR_P_BLOCK in sys_of(_flagged_task(factor_p=True, factor_v=True))
    # non-P arms: block absent, base _EDIT_SYSTEM unmodified
    assert _FACTOR_P_BLOCK not in sys_of(_flagged_task(factor_p=False, factor_v=False))
    assert _FACTOR_P_BLOCK not in sys_of(_flagged_task(factor_p=False, factor_v=True))


def test_factor_p_block_uses_visible_tests_vocabulary() -> None:
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    assert "visible tests" in _FACTOR_P_BLOCK
    assert "public tests" not in _FACTOR_P_BLOCK


def test_make_edit_task_without_flag_keeps_unmodified_edit_system() -> None:
    # a task with NO factor_p key (e.g. an un-armed task) gets the bare _EDIT_SYSTEM
    from agent_eval_lab.runners.f_candidate import _FACTOR_P_BLOCK

    edit = make_edit_task(_fake_task(), base_tree={"a.js": "x\n"})
    sys = next(m for m in edit.input.messages if m.role == "system").content
    assert _FACTOR_P_BLOCK not in sys
```

Add `from dataclasses import replace` to the test file's imports if not present (check the top of the file; the source uses `replace` but the test may not import it yet).

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_factor_p_block_present_only_on_prompt_and_both_arms -o addopts="" -q`
Expected: ImportError `cannot import name '_FACTOR_P_BLOCK'` — confirms the constant does not exist.

- [ ] **Step 3: Add `_FACTOR_P_BLOCK` to `f_candidate.py`**

In `src/agent_eval_lab/runners/f_candidate.py`, immediately after the `_EDIT_SYSTEM` constant (after line 59), add:

```python
# Factor P — context-gathering prompt nudges (item 003 §B.3). A discrete,
# attributable block appended to _EDIT_SYSTEM on the `prompt` and `both` arms
# ONLY (gated by initial_state["factor_p"] in make_edit_task). Glossary: it says
# "visible tests", never "public tests" (§11.4). bare/feedback keep the
# unmodified _EDIT_SYSTEM.
_FACTOR_P_BLOCK = (
    "Before editing, gather context. Read the full body of any method that a call "
    "or assertion you touch depends on — do not assume its contract from its name. "
    "Before adding a method, read the sibling methods in the same file so your "
    "addition matches their shape and conventions. Read the local conventions for "
    "this layer (its README, config, or nearest CLAUDE.md) before you write. Read "
    "the entire target file and the full set of visible tests that exercise it "
    "before your first edit. Change only what the task requires; leave every other "
    "file and layer untouched."
)
```

- [ ] **Step 4: Wire the gate into `make_edit_task`**

In `src/agent_eval_lab/runners/f_candidate.py`, replace the body of `make_edit_task` (lines 113-129) with:

```python
def make_edit_task(task: Task, *, base_tree: Mapping[str, str]) -> Task:
    """Recast an F task as a code-world edit task: swap the prose `bash` tool for
    the pure file-edit tools and seed the produced tree into `files`. The held-out
    verification and task identity are preserved verbatim.

    Factor P (item 003 §B.3): if initial_state["factor_p"] is truthy, append the
    attributable _FACTOR_P_BLOCK to the rebuilt _EDIT_SYSTEM. Factor V (§B.2): if
    initial_state["factor_v"] is truthy, additionally offer the run_tests tool name
    (its executor is item 005 — make_f_run_fn binds executor=None and refuses to
    drive a live V arm until then)."""
    state = task.initial_state or {}
    system = _EDIT_SYSTEM.format(tools=", ".join(F_EDIT_TOOL_NAMES))
    if state.get("factor_p"):
        system = f"{system}\n\n{_FACTOR_P_BLOCK}"
    tools = F_EDIT_TOOL_NAMES + (("run_tests",) if state.get("factor_v") else ())
    user = next((m for m in task.input.messages if m.role == "user"), None)
    messages = (MessageTurn(role="system", content=system),) + (
        (user,) if user is not None else ()
    )
    initial_state = {**state, "files": dict(base_tree)}
    return replace(
        task,
        input=TaskInput(messages=messages, available_tools=tools),
        initial_state=initial_state,
    )
```

- [ ] **Step 5: Run the new P tests**

Run: `python -m pytest tests/runners/test_f_candidate.py -k "factor_p or edit_system" -o addopts="" -q`
Expected: `3 passed`.

- [ ] **Step 6: Run the existing `make_edit_task` regression tests**

Run: `python -m pytest tests/runners/test_f_candidate.py -k "make_edit_task" -o addopts="" -q`
Expected: all pass (the existing `test_make_edit_task_seeds_files_and_swaps_in_edit_tools`, `test_make_edit_task_preserves_user_instruction_and_describes_tools`, `test_make_edit_task_does_not_mutate_source_or_base_tree` still pass — the un-flagged path is unchanged behavior).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(003): Factor P block appended in make_edit_task for P arms"
```

---

## Task 4: Factor-V tool surface preserved through `make_edit_task`

**Files:**
- Test: `tests/runners/test_f_candidate.py`
- (Source already handled in Task 3 Step 4 — this asserts the V surface invariant.)

- [ ] **Step 1: Write the failing test**

Add to `tests/runners/test_f_candidate.py`:

```python
def test_make_edit_task_offers_run_tests_only_on_v_arms() -> None:
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    non_v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=False), base_tree={"a.js": "x\n"}
    )
    assert "run_tests" in v_edit.input.available_tools
    # the edit tools are still all present on the V arm (run_tests is ADDED, not swapped)
    for name in F_EDIT_TOOL_NAMES:
        assert name in v_edit.input.available_tools
    assert "run_tests" not in non_v_edit.input.available_tools
```

- [ ] **Step 2: Run the test**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_make_edit_task_offers_run_tests_only_on_v_arms -o addopts="" -q`
Expected: `1 passed` (the source from Task 3 Step 4 already adds `run_tests` for `factor_v`).

- [ ] **Step 3: Commit**

```bash
git add tests/runners/test_f_candidate.py
git commit -m "test(003): V arms offer run_tests tool surface (executor deferred to 005)"
```

---

## Task 5: Task-scoped `run_uid` + collision-freeness

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py:145-159` (`make_f_run_fn` closure)
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing test for task-scoped run_uid**

Add to `tests/runners/test_f_candidate.py`:

```python
def test_run_uid_is_task_scoped(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    import httpx

    captured: list[str] = []

    def fake_run_single(**kwargs):
        captured.append(kwargs["run_uid"])
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="deepseek:deepseek-v4-pro",
        safety_cap=200,
        max_rounds=40,
    )
    edit = make_edit_task(
        _flagged_task(factor_p=True, factor_v=False), base_tree={"a.js": "x\n"}
    )
    run_fn(edit, 3)
    # {condition_id}__{task_id}__{run_index:04d}
    assert captured == ["deepseek:deepseek-v4-pro__t1__0003"]
    assert "__f__" not in captured[0]  # the old literal is gone
```

> `_flagged_task` builds on `_fake_task()` whose `id` is `"t1"`, so the expected uid embeds `t1`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_run_uid_is_task_scoped -o addopts="" -q`
Expected: FAIL — `captured == ['deepseek:deepseek-v4-pro__f__0003']` (the old `__f__` literal), assertion mismatch.

- [ ] **Step 3: Task-scope the run_uid in `make_f_run_fn`**

In `src/agent_eval_lab/runners/f_candidate.py`, in the `run_fn` closure inside `make_f_run_fn`, change line 156 from:

```python
            run_uid=f"{condition_id}__f__{run_index:04d}",
```

to:

```python
            run_uid=f"{condition_id}__{edit_task.id}__{run_index:04d}",
```

> `edit_task` is the closure's parameter; `make_edit_task` preserves the arm's `id` via `replace(task, ...)`, so `edit_task.id` is e.g. `f-f1-prompt`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_run_uid_is_task_scoped -o addopts="" -q`
Expected: `1 passed`.

- [ ] **Step 5: Write the collision-free test (12 task-arms × run_index in one condition)**

Add to `tests/runners/test_f_candidate.py`:

```python
def test_run_uid_collision_free_across_arms_in_one_condition(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    import httpx

    seen: list[str] = []

    def fake_run_single(**kwargs):
        seen.append(kwargs["run_uid"])
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    # simulate the 12 task-arms (3 bases x 4 arms) x k=5 in one condition's space
    arm_ids = [
        f"f-{b}-{a}"
        for b in ("f1", "f2", "f3")
        for a in ("bare", "prompt", "feedback", "both")
    ]
    for aid in arm_ids:
        # a minimal edit-task carrying the arm id; tree/flags irrelevant to the uid
        edit = replace(
            _fake_task(),
            id=aid,
            initial_state={**_fake_task().initial_state, "files": {}},
        )
        for k in range(5):
            run_fn(edit, k)
    assert len(seen) == 60  # 12 arms x k=5
    assert len(set(seen)) == 60  # all distinct -> no collision in the run space
```

- [ ] **Step 6: Run the collision test**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_run_uid_collision_free_across_arms_in_one_condition -o addopts="" -q`
Expected: `1 passed`.

- [ ] **Step 7: Update the `run_uid` docstring on `Trajectory`**

In `src/agent_eval_lab/records/trajectory.py`, update the `run_uid` field docstring (line 88) from:

```python
    run_uid: str | None = None
    """Per-run unique id: f"{condition_id}__{run_index:04d}" (§18.1)."""
```

to:

```python
    run_uid: str | None = None
    """Per-run unique id. B/D: f"{condition_id}__{run_index:04d}" (§18.1); F is
    task-scoped f"{condition_id}__{task_id}__{run_index:04d}" so 12 task-arms
    sharing a condition's run space cannot collide (item 003 §B.2/§11.8)."""
```

- [ ] **Step 8: Run the full f_candidate test module (regression)**

Run: `python -m pytest tests/runners/test_f_candidate.py -o addopts="" -q`
Expected: all non-skipped tests pass (the `requires_node` integration tests skip without node+repo+store; the unit tests — including the pre-existing `test_make_f_run_fn_forwards_max_rounds` — pass).

- [ ] **Step 9: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py src/agent_eval_lab/records/trajectory.py tests/runners/test_f_candidate.py
git commit -m "feat(003): task-scoped run_uid (collision-free across 12 arms)"
```

---

## Task 6: Guard a live V arm in `make_f_run_fn` (no fabricated V executor)

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py` (`run_fn` closure in `make_f_run_fn`)
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/runners/test_f_candidate.py`:

```python
def test_make_f_run_fn_refuses_live_v_arm_until_005(monkeypatch) -> None:
    """A V arm (factor_v=True) declares run_tests but has NO executor in 003.
    Driving it against the live loop must raise, not silently run a no-op V loop."""
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.runners.config import ProviderConfig
    import httpx

    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    v_edit = make_edit_task(
        _flagged_task(factor_p=False, factor_v=True), base_tree={"a.js": "x\n"}
    )
    with pytest.raises(NotImplementedError, match="Factor V"):
        run_fn(v_edit, 0)


def test_make_f_run_fn_runs_bare_and_prompt_arms_today(monkeypatch) -> None:
    """bare/prompt (factor_v=False) stay fully runnable in 003."""
    import agent_eval_lab.runners.f_candidate as fc
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.config import ProviderConfig
    import httpx

    def fake_run_single(**kwargs):
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
        )

    monkeypatch.setattr(fc, "run_single", fake_run_single)
    cfg = ProviderConfig(
        id="local", base_url="http://x/v1", api_key_env="", model_id="m"
    )
    client = httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    run_fn = fc.make_f_run_fn(
        config=cfg,
        http_client=client,
        temperature=0.0,
        max_tokens=64,
        condition_id="c",
        safety_cap=200,
        max_rounds=40,
    )
    for flags in ((False, False), (True, False)):  # bare, prompt
        edit = make_edit_task(
            _flagged_task(factor_p=flags[0], factor_v=flags[1]),
            base_tree={"a.js": "x\n"},
        )
        traj = run_fn(edit, 0)
        assert traj.stop_reason == "completed_natural"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m pytest tests/runners/test_f_candidate.py::test_make_f_run_fn_refuses_live_v_arm_until_005 -o addopts="" -q`
Expected: FAIL — no `NotImplementedError` is raised (the V arm currently runs with `executor=None`, producing a trajectory instead of raising).

- [ ] **Step 3: Add the V guard to the `run_fn` closure**

In `src/agent_eval_lab/runners/f_candidate.py`, update the `run_fn` closure inside `make_f_run_fn` so it refuses a live V arm before calling `run_single`. Replace the closure body (lines 145-159) with:

```python
    def run_fn(edit_task: Task, run_index: int) -> Trajectory:
        # Factor V's executor + sandbox is item 005. A V arm declares run_tests
        # (its tool SURFACE) but has no executor here; driving it against the live
        # loop would silently run a no-op V loop, so refuse explicitly. bare/prompt
        # (factor_v falsey) stay fully runnable today.
        if (edit_task.initial_state or {}).get("factor_v"):
            raise NotImplementedError(
                "Factor V executor is item 005; cannot drive a V arm "
                f"({edit_task.id!r}) against a live provider in 003"
            )
        return run_single(
            task=edit_task,
            registry=CODE_WORLD_TOOLS,
            config=config,
            http_client=http_client,
            run_index=run_index,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=code_world_apply,
            executor=None,
            run_uid=f"{condition_id}__{edit_task.id}__{run_index:04d}",
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )
```

> This keeps the task-scoped `run_uid` from Task 5 (do not revert it).

- [ ] **Step 4: Run both new tests**

Run: `python -m pytest tests/runners/test_f_candidate.py -k "live_v_arm or runs_bare_and_prompt" -o addopts="" -q`
Expected: `2 passed`.

- [ ] **Step 5: Re-run the collision-free test (it drives 12 arms incl. V arms)**

> The Task 5 collision test builds arm ids directly via `replace(_fake_task(), id=aid, initial_state={..., "files": {}})` — those `initial_state`s have NO `factor_v` key, so `.get("factor_v")` is falsey and the guard does not fire. Confirm it still passes after the guard lands:

Run: `python -m pytest tests/runners/test_f_candidate.py::test_run_uid_collision_free_across_arms_in_one_condition -o addopts="" -q`
Expected: `1 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(003): refuse live V arm until 005 wires the executor"
```

---

## Task 7: Regression — frozen M1 spec still verifies; no record/spec plumbing changed

**Files:**
- Verify only (no edit): `tests/experiments/test_m1_spec.py`, `tests/experiments/test_spec_hash.py`, `tests/records/test_serialize.py`, `tests/records/test_trajectory.py`, `tests/experiments/test_hydrate.py`, `tests/runners/test_b_isolation.py`

- [ ] **Step 1: Confirm `verify_spec_hash` still passes (the hashed schema is untouched)**

Run: `python -m pytest tests/experiments/test_m1_spec.py tests/experiments/test_spec_hash.py -o addopts="" -q`
Expected: all pass. Rationale: `m1_spec.py` enumerates conditions + metrics only (no F `task_id`s); the arm-as-task change lives entirely in the dataset builder + runner, so the spec's canonical bytes are unchanged.

- [ ] **Step 2: Confirm serialize / trajectory round-trip is unchanged (no `arm_id`, no new field)**

Run: `python -m pytest tests/records/test_serialize.py tests/records/test_trajectory.py -o addopts="" -q`
Expected: all pass. Rationale: 003 added no record field; `run_uid` is still a `str | None` that round-trips as-is — only its *value format* changed for F, which the readers key on as an opaque string.

- [ ] **Step 3: Confirm run_uid consumers (hydrate, b_isolation) still pass**

Run: `python -m pytest tests/experiments/test_hydrate.py tests/runners/test_b_isolation.py -o addopts="" -q`
Expected: all pass. Rationale: hydrate matches `run_uid` as an opaque string; `b_isolation.save_name_from_run_uid` slugs whatever string it gets (B path, unaffected by the F format change — the new F shape still slugs to a legal name).

- [ ] **Step 4: Confirm the report side needs no change (`pass^k` groups by `task_id`)**

Run: `python -c "import inspect, agent_eval_lab.metrics.reliability as r; print('by_task' in inspect.getsource(r.pass_pow_k))"`
Expected: `True`. Rationale: `pass_pow_k` / `task_reliability` group by `run.task_id` (reliability.py:43-47, 71-77); the four arms are four distinct `task_id`s, so per-arm `pass^k` falls out with no report-side plumbing (§B.2). No code change.

- [ ] **Step 5: Commit (no-op safety net — only if Steps 1-4 surfaced an unexpected edit)**

If Steps 1-4 all passed with no file changes, **skip this commit** (nothing to stage). This task is a verification gate, not a code change.

---

## Task 8: Whole-repo verification (CI parity) + final commit

**Files:** none (verification only)

- [ ] **Step 1: Run the full F + dataset test surface**

Run: `python -m pytest tests/datasets/test_f_tasks.py tests/runners/test_f_candidate.py -o addopts="" -q`
Expected: all pass (or skip for `requires_store`/`requires_node` without local artifacts) — **0 failed, 0 errors**.

- [ ] **Step 2: Run the whole suite**

Run: `python -m pytest -o addopts="" -q`
Expected: the pre-existing green suite stays green; the new 003 tests pass. **0 failed, 0 errors.**

- [ ] **Step 3: ruff format check over the WHOLE repo (CI runs this)**

Run: `python -m ruff format --check .`
Expected: `N files already formatted` (no diff). If it reports files that *would* be reformatted, run `python -m ruff format .`, then re-run `--check` and re-commit the affected files (stage explicitly — see Step 5).

- [ ] **Step 4: ruff lint**

Run: `python -m ruff check src/agent_eval_lab/datasets/f_tasks.py src/agent_eval_lab/runners/f_candidate.py src/agent_eval_lab/records/trajectory.py`
Expected: `All checks passed!`

- [ ] **Step 5: Final commit (only if Step 3 reformatted anything)**

```bash
# stage ONLY the files this item touched — never `git add -A` / `git add .`
git add src/agent_eval_lab/datasets/f_tasks.py src/agent_eval_lab/runners/f_candidate.py src/agent_eval_lab/records/trajectory.py tests/datasets/test_f_tasks.py tests/runners/test_f_candidate.py
git commit -m "style(003): ruff format f-ablation arm-as-task files"
```

---

## Self-review against the spec

**Spec coverage:**
- Arm-as-task structure (12 ids, suffix-named) → Task 1.
- Four arms share byte-identical tree-driving `initial_state` + same `verification` → Task 2.
- 2×2 factor mapping (`bare`/`prompt`/`feedback`/`both`) → Task 1 (`_ARM_FACTORS`) + Task 2 (asserted).
- M2 mechanism mirrored (shared verification, shared base messages, arm diffs on top) → Task 1 `_arm`.
- Factor P: discrete attributable block appended to `_EDIT_SYSTEM`, prompt/both only, named isolated constant, "visible tests" vocab, bare/feedback unmodified → Task 3.
- Task-scoped `run_uid` `{condition_id}__{task_id}__{run_index}` replacing `__f__` literal; collision-free across (condition × 12 arms × run_index) → Task 5.
- `run_uid` consumers stay correct (hydrate, b_isolation, serialize) → Task 7 Steps 2-3.
- No `arm_id`/`ArmDef`/`tool_set_hash`/`ConditionDef`/`ExperimentSpec`/serialize change; `verify_spec_hash` passes → Task 7 Steps 1-2 (and no such field appears anywhere in this plan).
- `report-m1` groups by `task_id` (per-arm `pass^k` for free, no report plumbing) → Task 7 Step 4 (confirm-only).
- V scope boundary: V arms establish identity + tool surface only; no live V loop; bare/prompt runnable → Task 4 + Task 6 (D2).
- Candidate-tree enrichment NOT done (arms share whatever the base tree is today, byte-identical) → Task 1/2 carry only `target_paths` (today's tree driver); no enrichment.
- Carry-forward (002): per-task F `max_rounds` override path reachable → Task 2 Step 3 (D4).

**Placeholder scan:** none — every code/test step shows full content; the Factor-P block, the 12-arm builder, and the run_uid change are typed verbatim.

**Type consistency:** `build_f_task_arms` / `_arm` / `_ARM_FACTORS` / `_V_TOOL` / `_FACTOR_P_BLOCK` / `_flagged_task` names are used identically across tasks. The arm-id format `f-{base}-{arm}` and the uid format `{condition_id}__{task_id}__{run_index:04d}` are consistent everywhere. `make_edit_task` reads `factor_p`/`factor_v` from `initial_state`; the builder writes exactly those keys.

**V-tool representation decision (D2):** declare `run_tests` in V arms' `available_tools` + `initial_state["factor_v"]=True` now (arm identity is real), executor binding deferred to 005, with a `NotImplementedError` guard preventing a live V run — `bare`/`prompt` stay runnable, no fabricated V executor.
