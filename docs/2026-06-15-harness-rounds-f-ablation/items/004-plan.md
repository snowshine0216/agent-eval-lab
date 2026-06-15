# Item 004 — Candidate-tree enrichment + overlay-disjointness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich each F **ablation arm's** candidate tree with a curated context set (siblings + readable source) from the pinned base SHA, identically across all four arms, and add a per-task overlay-disjointness invariant + unit test so enrichment can never collide with the held-out node oracle's grade-time overlay.

**Architecture:** The arm builder (`build_f_task_arms`) writes a new `context_paths` tuple onto each arm's `initial_state` (production `build_f_tasks` does NOT — it stays minimal). `build_candidate_tree` reads `context_paths` and `git show`s each path at the pinned SHA into the seeded tree, on top of the existing target-path/F3-causal-layer logic. A pure predicate `seeded_held_out_disjoint(seeded_paths, held_out_files)` reuses the existing `prefix_collision` helper; a unit test asserts disjointness for every F task's `NodeExecutionSpec(s)`.

**Tech Stack:** Python 3.12, dataclasses, pytest, `git show` (read-only, pinned SHA `5b0c13a6`), local web-dossier repo at `~/Documents/Repository/web-dossier`.

---

## Background — read before starting

- **Spec:** `docs/2026-06-15-harness-rounds-f-ablation/items/004-spec.md` (authoritative acceptance criteria).
- **Design:** `docs/superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md` — §B.5 (enrichment + curation), §10.4 / round-3 row #4 (overlay-disjointness invariant + unit test), §11.6 (curation rule), Part C (per-subset F1/F2/F3), Part G step 4.
- **Pinned base SHA:** `CANDIDATE_BASE_SHA = "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505"` in `src/agent_eval_lab/runners/f_run.py:24`. The full SHA is what `git show` consumes; `f-f3` dispatch matches on `task.id`. m2021 HEAD is never read (D32).
- **The collision predicate:** `prefix_collision(new_path, existing_path) -> bool` in `src/agent_eval_lab/tools/code_world.py:126`. It returns **False** for identical spellings (a *displacement*, e.g. both trees carry `tests/wdio/package.json`) and **True** only when two paths share a canonical prefix but spell it differently. **Reuse it — do not reimplement** (this is the project's single collision predicate; `graders/node_execution.overlay_node_oracle` already reuses it).
- **The overlay:** `overlay_node_oracle(base_tree, held_out_files)` (`src/agent_eval_lab/graders/node_execution.py:40`) returns `NodeOverlayCollision` (→ `tree_collision` error in `runners/node_oracle_edge.py:36`) if any seeded base path collides with any held-out path. A silent collision turns an arm's runs into `agent_failure / tree_collision`, polluting the comparison (§10.4).
- **`held_out_files` source:** `collect_node_execution_specs(verification)` (`src/agent_eval_lab/graders/node_execution.py:71`) returns the `NodeExecutionSpec(s)` of a task; each spec's `held_out_files` is the dict of paths the oracle overlays. F1/F2 have one spec; F3 has two (golden + causal guard).

## Concrete context set (enumerated from the local repo at SHA `5b0c13a6`)

These exact paths are chosen below and hard-coded into `build_f_task_arms`. All verified to exist and be non-empty at the pinned SHA via `git show`.

- **F1** (`f-f1-*`, target = `Snapshots_SendBackground.spec.js` + `LibraryNotification.js`; held-out = `tests/wdio/f1.held_out.test.js`). Context set — three **small sibling page-objects** in `tests/wdio/pageObjects/common/` that surface the `waitFor*({ timeout, timeoutMsg })` poll/wait convention (so P's "read the siblings to match their shape" directive is non-vacuous):
  - `tests/wdio/pageObjects/common/Alert.js` (3.4 KB, 4 `waitFor*`)
  - `tests/wdio/pageObjects/common/SearchBox.js` (4.0 KB, 4 `waitFor*` with explicit `timeout`/`timeoutMsg`)
  - `tests/wdio/pageObjects/common/Panel.js` (2.1 KB, 2 `waitFor*`)
  - **EXCLUDED:** the held-out throw-on-timeout golden (`f1.held_out.test.js`, D19) and `BasePage.js` (87 KB; its inherited browser-driver `waitFor*` wrappers do not surface the *poll-and-throw* pattern and would bloat the tree). The discriminating behavior — throw-on-timeout — is asserted only in the held-out test, never in these siblings.
- **F2** (`f-f2-*`, target = `tests/wdio/wdio.conf.ts`; held-out = `tests/wdio/f2.held_out.test.js`). Context set — the **`analyzeFailure` source module** so its two-field return shape (`{ signal, confidence }`) is **readable from the source** (§C / §B.5):
  - `tests/wdio/utils/failure-analysis/index.js` (10.6 KB — exports `analyzeFailure`, the exact symbol `wdio.conf.ts:34` imports; its JSDoc says `@returns {Promise<{ signal: string, confidence: string }>}` and its body ends `return { signal: signal.signal, confidence: signal.confidence }`).
  - **EXCLUDED:** `tests/wdio/utils/failure-analysis/__tests__/index.test.js` and `.../compose.test.js` — both **assert the two-field split** (`assert.equal(result.signal, …)` + `assert.equal(result.confidence, 'medium')`), i.e. the discriminating behavior (§11.6). The source makes the shape *discoverable*; only the held-out `f2.held_out.test.js` asserts the `wdio.conf.ts` summary surfaces both fields.
- **F3** (`f-f3-*`, target = `report-to-allure.js`; held-out golden = `.../__tests__/report-to-allure.test.js`). **No new context paths** (`context_paths = ()`). `_f3_candidate_tree` (`f_candidate.py:87`) already seeds the entire `tests/wdio/utils/failure-analysis/` layer **minus** `F3_TEST_REL`. Audited every other seeded `__tests__/*.test.js`: none asserts the F3 discriminating behavior (cap + skip-when-empty + highlight-only-problem-requests) — the `cap`/`summary` substrings in `index.test.js`/`redact.test.js` are `capture`/`captureFn`/`summarizeNetwork`/`MAX_DEPTH`, unrelated to the Allure attachment cap. The cap+summary contract is asserted **only** in the held-out golden. The F3 acceptance is therefore satisfied by a *test that confirms* this (Task 4), not by new files.

## Attach-point decision

Enrichment attaches via a new `context_paths` tuple on **`build_f_task_arms`'s arm `initial_state` ONLY**, consumed by `build_candidate_tree`. Rationale:
- **Byte-identical across arms (preserved):** `context_paths` is computed once per base and passed to all four arms' `_arm(...)` calls → the four arms of a base get the same `context_paths` → the same enriched tree. `tests/datasets/test_f_tasks.py::test_four_arms_of_a_base_share_verification_and_tree_state` is extended to assert `context_paths` equality too.
- **Production stays correct:** `build_f_tasks` (used by `m1_spec` / the production CLI at `cli.py:893`) sets **no** `context_paths`; `build_candidate_tree`/`prefix_candidate_tree` default to `()` → production trees are byte-unchanged. Existing `prefix_candidate_tree`/`_f3_candidate_tree` integration tests stay green.
- **No frozen-record / `verify_spec_hash` impact:** `compute_spec_hash` (`experiments/spec_hash.py:57`) hashes only the `ExperimentSpec` (conditions/metrics/families) — it never reads `Task.initial_state`. Adding a key to arm `initial_state` cannot move any frozen spec hash.
- **No `arm_id`/`ArmDef`/spec field:** `context_paths` is plain task data on `initial_state`, consistent with item 003's arm-as-task pattern.

---

## File Structure

- **Modify** `src/agent_eval_lab/runners/f_candidate.py` — `build_candidate_tree` reads `context_paths` and seeds them (on the non-F3 path); F3 path unchanged. Add the pure `seeded_held_out_disjoint` predicate.
- **Modify** `src/agent_eval_lab/datasets/f_tasks.py` — define per-base `context_paths`; thread through `_arm` → arm `initial_state`. `build_f_tasks` (production) untouched.
- **Modify** `tests/runners/test_f_candidate.py` — unit tests for `context_paths` enrichment (pure, no repo) + a node-gated integration test that the enriched F1 arm tree carries the chosen siblings; the disjointness predicate unit tests.
- **Modify** `tests/datasets/test_f_tasks.py` — assert each arm carries the expected `context_paths`, four arms share them byte-identical, production `build_f_tasks` carries none.
- **Create** `tests/runners/test_f_overlay_disjoint.py` — the §10.4 invariant test over every F task's `NodeExecutionSpec(s)`.

---

### Task 1: `context_paths` enrichment in `build_candidate_tree` (pure unit, no repo)

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py`
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing unit test** (no repo — injects the `_git_show` reader via monkeypatch)

Add to `tests/runners/test_f_candidate.py` (after the `make_edit_task` block, before `# ---- run_f_candidate`):

```python
# ---- build_candidate_tree context_paths enrichment (pure, no repo) --------


def _task_with_context(context_paths: tuple[str, ...]) -> Task:
    base = _fake_task()
    return replace(
        base,
        initial_state={
            "repo": "x",
            "candidate_base_sha": "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505",
            "target_paths": ("src/a.js",),
            "context_paths": context_paths,
        },
    )


def test_build_candidate_tree_seeds_context_paths(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    # stub the SHA reader used by BOTH the prefix path and the enrichment
    monkeypatch.setattr(fc, "_git_show", lambda repo, rel: f"// {rel}\n")
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": f"// {a[0][-1].split(':')[-1]}\n"})(),
    )
    task = _task_with_context(("sib/One.js", "sib/Two.js"))
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    # target path + both context paths are present; pkg.json still seeded
    assert "src/a.js" in tree
    assert tree["sib/One.js"] == "// sib/One.js\n"
    assert tree["sib/Two.js"] == "// sib/Two.js\n"
    assert tree["tests/wdio/package.json"] == '{"type":"module"}\n'


def test_build_candidate_tree_empty_context_paths_is_minimal(monkeypatch) -> None:
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    monkeypatch.setattr(fc, "_git_show", lambda repo, rel: f"// {rel}\n")
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": "x\n"})(),
    )
    task = _task_with_context(())
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    # no context paths -> only target + pkg.json (production-shape)
    assert set(tree) == {"src/a.js", "tests/wdio/package.json"}


def test_build_candidate_tree_missing_context_key_defaults_to_none(monkeypatch) -> None:
    # production build_f_tasks sets NO context_paths key -> must not raise
    import agent_eval_lab.runners.f_candidate as fc
    import agent_eval_lab.runners.f_run as fr

    monkeypatch.setattr(fr, "subprocess", fr.subprocess)
    monkeypatch.setattr(
        fr.subprocess,
        "run",
        lambda *a, **k: type("R", (), {"stdout": "x\n"})(),
    )
    base = _fake_task()
    task = replace(
        base,
        initial_state={
            "repo": "x",
            "candidate_base_sha": "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505",
            "target_paths": ("src/a.js",),
        },
    )
    tree = fc.build_candidate_tree(task, repo=Path("/nonexistent"))
    assert set(tree) == {"src/a.js", "tests/wdio/package.json"}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/runners/test_f_candidate.py -k context -o addopts="" -q`
Expected: FAIL — `test_build_candidate_tree_seeds_context_paths` fails with `KeyError: 'sib/One.js'` (the enrichment is not yet wired; the bare `prefix_candidate_tree` returns only target + pkg.json).

- [ ] **Step 3: Implement the enrichment in `build_candidate_tree`**

In `src/agent_eval_lab/runners/f_candidate.py`, replace the `build_candidate_tree` function (currently lines 118–126) with:

```python
def build_candidate_tree(task: Task, *, repo: Path) -> dict[str, str]:
    """Seed the candidate workspace at the pinned base SHA (D32).

    F1/F2 are self-contained in their target paths; F3 additionally needs the
    failure-analysis causal layer present so the held-out guard tests can run.

    Ablation arms (item 004 §B.5) additionally carry `initial_state['context_paths']`
    — a curated context set (siblings + readable source) materialized identically
    across all four arms from the pinned SHA so Factor P's read-the-context directives
    are non-vacuous. Production `build_f_tasks` sets no context_paths, so its trees
    stay minimal. The held-out golden grading test is never seeded (D19); the
    overlay-disjointness invariant (§10.4, seeded_held_out_disjoint) guarantees a
    context path can never collide with a held-out path.
    """
    if task.id == "f-f3" or task.id.startswith("f-f3-"):
        return _f3_candidate_tree(task, repo=repo)
    tree = dict(prefix_candidate_tree(task, repo=repo))
    for rel in (task.initial_state or {}).get("context_paths", ()):
        tree[rel] = _git_show(repo, rel)
    return tree
```

(Note: `_git_show` already exists at `f_candidate.py:78`; `prefix_candidate_tree` is already imported at line 33.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/runners/test_f_candidate.py -k context -o addopts="" -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the whole f_candidate suite to confirm no regression**

Run: `python -m pytest tests/runners/test_f_candidate.py -o addopts="" -q`
Expected: PASS — previously-passing unit tests still pass; the repo-gated integration tests skip if node/repo absent (`X passed, N skipped`).

- [ ] **Step 6: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(004): build_candidate_tree seeds context_paths enrichment"
```

---

### Task 2: Per-base `context_paths` on the ablation arms (`build_f_task_arms`)

**Files:**
- Modify: `src/agent_eval_lab/datasets/f_tasks.py`
- Test: `tests/datasets/test_f_tasks.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/datasets/test_f_tasks.py` (after `test_f_tasks_carry_the_repo_relative_target_paths`):

```python
# the concrete context sets enumerated from web-dossier @ 5b0c13a6 (004 §B.5/§C)
_F1_CONTEXT = (
    "tests/wdio/pageObjects/common/Alert.js",
    "tests/wdio/pageObjects/common/SearchBox.js",
    "tests/wdio/pageObjects/common/Panel.js",
)
_F2_CONTEXT = ("tests/wdio/utils/failure-analysis/index.js",)
_F3_CONTEXT: tuple[str, ...] = ()  # F3 layer already broad; no new context paths


@requires_store
def test_arms_carry_the_curated_context_paths() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for arm in ("bare", "prompt", "feedback", "both"):
        assert arms[f"f-f1-{arm}"].initial_state["context_paths"] == _F1_CONTEXT
        assert arms[f"f-f2-{arm}"].initial_state["context_paths"] == _F2_CONTEXT
        assert arms[f"f-f3-{arm}"].initial_state["context_paths"] == _F3_CONTEXT


@requires_store
def test_four_arms_of_a_base_share_context_paths() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for base in ("f1", "f2", "f3"):
        suffixes = ("bare", "prompt", "feedback", "both")
        group = [arms[f"f-{base}-{s}"] for s in suffixes]
        ref = group[0].initial_state["context_paths"]
        for t in group[1:]:
            assert t.initial_state["context_paths"] == ref  # byte-identical


@requires_store
def test_production_f_tasks_carry_no_context_paths() -> None:
    # enrichment is for the ablation arms only; production stays minimal
    for t in build_f_tasks(evaluator_store=_STORE):
        assert "context_paths" not in t.initial_state
```

Also extend the existing `test_four_arms_of_a_base_share_verification_and_tree_state` (do NOT duplicate — add one assertion inside its `for t in group[1:]:` loop, after the `target_paths` assertion):

```python
            assert t.initial_state["context_paths"] == ref.initial_state["context_paths"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/datasets/test_f_tasks.py -k "context_paths or share_verification" -o addopts="" -q`
Expected: FAIL — `KeyError: 'context_paths'` (arms have no such key yet).

- [ ] **Step 3: Implement the per-base context sets and thread them through `_arm`**

In `src/agent_eval_lab/datasets/f_tasks.py`:

(a) After the `_F3_USER = (...)` block (around line 58), add the context-set constants:

```python
# Curated context sets (item 004 §B.5/§C) — additional paths seeded into the
# ABLATION-arm candidate trees beyond target_paths, read identically across all
# four arms from the pinned base SHA (5b0c13a6; m2021 never read). Production
# build_f_tasks seeds none. Each path excludes the held-out golden (D19) and any
# visible test that asserts the discriminating behavior (§11.6).
_F1_CONTEXT_PATHS: tuple[str, ...] = (
    # small sibling page-objects that surface the waitFor*({timeout,timeoutMsg})
    # convention; the throw-on-timeout golden stays held-out.
    "tests/wdio/pageObjects/common/Alert.js",
    "tests/wdio/pageObjects/common/SearchBox.js",
    "tests/wdio/pageObjects/common/Panel.js",
)
_F2_CONTEXT_PATHS: tuple[str, ...] = (
    # analyzeFailure's source so its {signal, confidence} return shape is readable
    # from the source; the two tests that ASSERT the split are excluded.
    "tests/wdio/utils/failure-analysis/index.js",
)
# F3's tree is already broad (_f3_candidate_tree seeds the whole causal layer
# minus F3_TEST_REL); no seeded test asserts the cap+summary, so no new context.
_F3_CONTEXT_PATHS: tuple[str, ...] = ()
```

(b) Change `_arm`'s signature and `initial_state` to carry `context_paths`. Replace `_arm` (lines 106–138) with:

```python
def _arm(
    *,
    base: str,
    arm: str,
    user: str,
    verification,
    target_paths: tuple[str, ...],
    context_paths: tuple[str, ...],
) -> Task:
    """One arm-task of a base F task: same held-out verification + same
    tree-driving initial_state as its three siblings, differing only in the
    factor_p/factor_v flags (read by make_edit_task) and available_tools.

    initial_state carries `context_paths` (item 004 §B.5) — the curated context
    set seeded identically across all four arms by build_candidate_tree."""
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
            "context_paths": context_paths,
            "factor_p": factor_p,
            "factor_v": factor_v,
        },
    )
```

(c) Thread the context sets through `build_f_task_arms` (lines 164–187). Replace its `bases` tuple and the comprehension with:

```python
def build_f_task_arms(*, evaluator_store: Path) -> tuple[Task, ...]:
    """The 12 F task-arms (3 base tasks x 4 arms) for the harness-factor ablation
    (item 003 §B.1). Each base's four arms share that base's held-out
    VerificationSpec and tree-driving initial_state byte-for-byte — including the
    curated context_paths (item 004 §B.5) — and differ ONLY in Factor P (a
    system-prompt block, gated by initial_state['factor_p']) and Factor V (the
    declared tool surface, initial_state['factor_v'] + available_tools). The arm
    IS the task_id — no arm_id, no spec change."""
    bases = (
        (
            "f1",
            _F1_USER,
            build_f1_verification(evaluator_store),
            (F1_SPEC_REL, F1_PAGE_REL),
            _F1_CONTEXT_PATHS,
        ),
        (
            "f2",
            _F2_USER,
            build_f2_verification(evaluator_store),
            (F2_CONF_REL,),
            _F2_CONTEXT_PATHS,
        ),
        (
            "f3",
            _F3_USER,
            build_f3_verification(evaluator_store),
            (F3_SOURCE_REL,),
            _F3_CONTEXT_PATHS,
        ),
    )
    return tuple(
        _arm(
            base=base,
            arm=arm,
            user=user,
            verification=verification,
            target_paths=paths,
            context_paths=context_paths,
        )
        for base, user, verification, paths, context_paths in bases
        for arm in ("bare", "prompt", "feedback", "both")
    )
```

(Leave `_task` and `build_f_tasks` UNCHANGED — production tasks carry no `context_paths`.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/datasets/test_f_tasks.py -o addopts="" -q`
Expected: PASS (all `@requires_store` tests pass if the golden store exists; otherwise they skip — run with the store present to confirm).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/datasets/f_tasks.py tests/datasets/test_f_tasks.py
git commit -m "feat(004): curated context_paths on the 12 F ablation arms"
```

---

### Task 3: The overlay-disjointness predicate (pure)

**Files:**
- Modify: `src/agent_eval_lab/runners/f_candidate.py`
- Test: `tests/runners/test_f_candidate.py`

- [ ] **Step 1: Write the failing unit tests** for the pure predicate

Add to `tests/runners/test_f_candidate.py` (after the context-paths block from Task 1):

```python
# ---- seeded_held_out_disjoint predicate (pure, §10.4) ---------------------


def test_seeded_held_out_disjoint_true_for_disjoint_paths() -> None:
    from agent_eval_lab.runners.f_candidate import seeded_held_out_disjoint

    seeded = ("tests/wdio/utils/failure-analysis/report-to-allure.js",)
    held_out = {
        "tests/wdio/utils/failure-analysis/__tests__/report-to-allure.test.js": "x"
    }
    assert seeded_held_out_disjoint(seeded, held_out) is True


def test_seeded_held_out_disjoint_allows_identical_displaced_path() -> None:
    # identical spelling (e.g. tests/wdio/package.json in both) is a DISPLACEMENT,
    # not a prefix_collision -> disjoint=True (the overlay overwrites, no error).
    from agent_eval_lab.runners.f_candidate import seeded_held_out_disjoint

    seeded = ("tests/wdio/package.json", "src/a.js")
    held_out = {"tests/wdio/package.json": "{}", "a.test.js": "x"}
    assert seeded_held_out_disjoint(seeded, held_out) is True


def test_seeded_held_out_disjoint_false_on_canonical_prefix_collision() -> None:
    # same canonical prefix, different spelling (case) -> collision -> not disjoint
    from agent_eval_lab.runners.f_candidate import seeded_held_out_disjoint

    seeded = ("tests/wdio/Foo.js",)
    held_out = {"tests/wdio/foo.js/held.test.js": "x"}
    assert seeded_held_out_disjoint(seeded, held_out) is False
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/runners/test_f_candidate.py -k disjoint -o addopts="" -q`
Expected: FAIL — `ImportError: cannot import name 'seeded_held_out_disjoint'`.

- [ ] **Step 3: Implement the predicate** (reuse `prefix_collision` — do not reimplement)

In `src/agent_eval_lab/runners/f_candidate.py`, add the import near the top imports (after the `from agent_eval_lab.tasks.schema import Task, TaskInput` line at 37) :

```python
from agent_eval_lab.tools.code_world import prefix_collision
```

Then add the predicate (place it just below `build_candidate_tree`):

```python
def seeded_held_out_disjoint(
    seeded_paths: Sequence[str], held_out_files: Mapping[str, str]
) -> bool:
    """True iff no seeded (candidate-visible) path collides with any held-out
    oracle path under `prefix_collision` (§10.4).

    Pure. The held-out node oracle overlays `held_out_files` over the candidate
    base tree at grade time; `overlay_node_oracle` raises NodeOverlayCollision ->
    `tree_collision` error if a seeded path canonically prefix-collides with a
    held-out path. Identical spellings are DISPLACEMENTS (overwrite allowed), not
    collisions, so they are disjoint. Reuses the project's single collision
    predicate (tools/code_world.prefix_collision) — never reimplemented."""
    return not any(
        prefix_collision(seeded, oracle)
        for seeded in seeded_paths
        for oracle in held_out_files
    )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/runners/test_f_candidate.py -k disjoint -o addopts="" -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/runners/f_candidate.py tests/runners/test_f_candidate.py
git commit -m "feat(004): seeded_held_out_disjoint predicate (reuses prefix_collision)"
```

---

### Task 4: The §10.4 invariant test over every F task's `NodeExecutionSpec(s)`

**Files:**
- Create: `tests/runners/test_f_overlay_disjoint.py`

This is the **mandatory** unit test (spec acceptance: "Enforce the invariant with a unit test over each F task's `NodeExecutionSpec(s)`"). It must fail if a future enrichment introduces a colliding path. It does NOT need a live model or network; it does need the golden store to build the tasks' verifications (`@requires_store`), and the local repo to materialize the seeded trees (`@requires_repo`).

- [ ] **Step 1: Write the test file**

Create `tests/runners/test_f_overlay_disjoint.py`:

```python
"""§10.4 overlay-disjointness invariant: every seeded (candidate-visible) path of
an F task must be disjoint under `prefix_collision` from that task's held-out
oracle paths, so enrichment can never turn an arm's runs into tree_collision.

Covers BOTH builders' F tasks (production build_f_tasks + the 12 ablation arms).
For each task we materialize its real seeded tree (build_candidate_tree at the
pinned base SHA) and assert seeded_held_out_disjoint against EACH NodeExecutionSpec
collected from the task's verification.
"""

from pathlib import Path

import pytest

from agent_eval_lab.datasets.f_tasks import build_f_task_arms, build_f_tasks
from agent_eval_lab.graders.node_execution import collect_node_execution_specs
from agent_eval_lab.runners.f_candidate import (
    build_candidate_tree,
    seeded_held_out_disjoint,
)

_REPO = Path.home() / "Documents/Repository/web-dossier"
_STORE = (
    Path.home()
    / "Documents/Repository/agent-eval-lab/evaluator-only/web-dossier-golden"
)

requires_repo = pytest.mark.skipif(
    not _REPO.exists()
    or not (_STORE / "golden-files" / "f1.held_out.test.js").exists(),
    reason="local web-dossier repo + golden store required",
)


def _all_f_tasks():
    return list(build_f_tasks(evaluator_store=_STORE)) + list(
        build_f_task_arms(evaluator_store=_STORE)
    )


@requires_repo
def test_every_f_task_seeded_paths_disjoint_from_held_out() -> None:
    tasks = _all_f_tasks()
    assert len(tasks) == 3 + 12  # production trio + 12 arms
    for task in tasks:
        tree = build_candidate_tree(task, repo=_REPO)
        seeded = tuple(tree)  # the candidate-visible paths actually seeded
        specs = collect_node_execution_specs(task.verification)
        assert specs, f"{task.id} has no NodeExecutionSpec to check"
        for spec in specs:
            assert seeded_held_out_disjoint(seeded, spec.held_out_files), (
                f"{task.id}: seeded paths collide with held-out "
                f"{sorted(spec.held_out_files)} under prefix_collision"
            )


@requires_repo
def test_f3_held_out_golden_never_in_seeded_tree() -> None:
    # belt-and-suspenders for D19: the F3 golden grading test is never seeded
    from agent_eval_lab.datasets.f3_oracle import F3_TEST_REL

    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    for arm in ("bare", "prompt", "feedback", "both"):
        tree = build_candidate_tree(arms[f"f-f3-{arm}"], repo=_REPO)
        assert F3_TEST_REL not in tree


@requires_repo
def test_f1_arm_tree_carries_the_curated_siblings() -> None:
    # the enrichment actually lands the chosen F1 siblings in the arm tree
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    tree = build_candidate_tree(arms["f-f1-bare"], repo=_REPO)
    assert "tests/wdio/pageObjects/common/Alert.js" in tree
    assert "tests/wdio/pageObjects/common/SearchBox.js" in tree
    assert "tests/wdio/pageObjects/common/Panel.js" in tree
    # the held-out throw-on-timeout golden is NOT seeded
    assert "tests/wdio/f1.held_out.test.js" not in tree


@requires_repo
def test_f2_arm_tree_carries_analyzeFailure_source() -> None:
    arms = {t.id: t for t in build_f_task_arms(evaluator_store=_STORE)}
    tree = build_candidate_tree(arms["f-f2-bare"], repo=_REPO)
    assert "tests/wdio/utils/failure-analysis/index.js" in tree
    # the two visible tests that ASSERT the signal+confidence split are NOT seeded
    assert (
        "tests/wdio/utils/failure-analysis/__tests__/index.test.js" not in tree
    )
    assert (
        "tests/wdio/utils/failure-analysis/__tests__/compose.test.js" not in tree
    )
```

- [ ] **Step 2: Run the test to verify it passes** (repo + store present)

Run: `python -m pytest tests/runners/test_f_overlay_disjoint.py -o addopts="" -q`
Expected: PASS (4 passed) when the local repo + golden store exist. If they are absent the tests **skip** (`4 skipped`) — that is acceptable for CI but the author MUST run it once locally with the repo present and see `4 passed` before committing.

- [ ] **Step 3: Sanity-check the invariant actually bites** (temporary, do NOT commit)

Temporarily add a deliberately-colliding context path to `_F1_CONTEXT_PATHS` in `f_tasks.py` — e.g. `"tests/wdio/f1.held_out.test.js"` (identical to the F1 held-out path → this is a *displacement* not a collision, so instead use a case-variant: `"tests/wdio/F1.held_out.test.js"`). Re-run:

Run: `python -m pytest tests/runners/test_f_overlay_disjoint.py::test_every_f_task_seeded_paths_disjoint_from_held_out -o addopts="" -q`
Expected: FAIL — `f-f1-bare: seeded paths collide with held-out [...] under prefix_collision`.
Then **revert** the temporary edit and re-run to confirm PASS again. (This proves the test fails on a future colliding enrichment, per the spec.)

- [ ] **Step 4: Commit**

```bash
git add tests/runners/test_f_overlay_disjoint.py
git commit -m "test(004): overlay-disjointness invariant over every F NodeExecutionSpec (§10.4)"
```

---

### Task 5: Whole-repo verification (lint + format + full suite)

**Files:** none (verification only)

- [ ] **Step 1: Run ruff lint over the whole repo**

Run: `ruff check .`
Expected: `All checks passed!` (CI runs this whole-repo).

- [ ] **Step 2: Run ruff format check over the whole repo**

Run: `ruff format --check .`
Expected: `N files already formatted` (no diff). If it reports files to reformat, run `ruff format .`, re-stage the affected files, and amend the relevant commit.

- [ ] **Step 3: Run the full test suite**

Run: `python -m pytest -o addopts="" -q`
Expected: the pre-existing pass count plus the new tests; **zero failures**. Repo/store-gated tests skip if the local repo/store are absent (note the skip count). Run once locally WITH the repo + store present to confirm the new node-gated tests pass (not just skip).

- [ ] **Step 4: Final focused re-run of the item's tests**

Run: `python -m pytest tests/runners/test_f_candidate.py tests/datasets/test_f_tasks.py tests/runners/test_f_overlay_disjoint.py -o addopts="" -q`
Expected: all pass / skip, zero failures.

---

## Self-Review — spec acceptance criteria → task map

| Spec acceptance criterion (004-spec.md) | Task |
|---|---|
| **§B.5** Per F base task, define a context set read from the pinned SHA via `git show 5b0c13a6:<path>` | Task 2 (`_F1/_F2/_F3_CONTEXT_PATHS`) + Task 1 (`build_candidate_tree` reads them via `_git_show`) |
| **§B.5** Enriched tree materialized byte-identically across all four arms | Task 2 (`context_paths` set once per base, shared by all four `_arm` calls) + `test_four_arms_of_a_base_share_context_paths` |
| **§B.5** Enrichment lives in the candidate-tree-building path, not the prompt, not a per-arm difference | Task 1 (`build_candidate_tree`) — `context_paths` is identical across arms |
| **§11.6** Include what Factor P names: sibling modules, conventions, visible tests | Task 2: F1 siblings (`Alert/SearchBox/Panel`), F2 `analyzeFailure` source; F3 layer already broad |
| **§11.6** Exclude oracle/golden (D19) + visible tests asserting the discriminating behavior | Task 2 excludes `f1.held_out.test.js`, F2 `index.test.js`/`compose.test.js`; Task 4 asserts they are absent |
| **§C / F1** waitFor* siblings + (target spec already seeded) | Task 2 `_F1_CONTEXT_PATHS`; Task 4 `test_f1_arm_tree_carries_the_curated_siblings` |
| **§C / F2** `analyzeFailure` source readable, exclude the two-field-split assertion | Task 2 `_F2_CONTEXT_PATHS`; Task 4 `test_f2_arm_tree_carries_analyzeFailure_source` |
| **§C / F3** confirm cap+summary golden stays held-out; do not newly reveal | Task 2 `_F3_CONTEXT_PATHS = ()`; Task 4 `test_f3_held_out_golden_never_in_seeded_tree` |
| **§10.4** Per F task, seeded ∩ held-out = ∅ under `prefix_collision`; enrichment never adds a displaced/overlaid path | Task 3 (`seeded_held_out_disjoint`, reuses `prefix_collision`) + Task 4 invariant test |
| **§10.4** Unit test over each F task's `NodeExecutionSpec(s)`; fails on a future colliding path | Task 4 (`test_every_f_task_seeded_paths_disjoint_from_held_out` + the Step-3 bite-check) |
| **Constraint** Preserve 003's byte-identical-tree invariant | Task 2 extends `test_four_arms_of_a_base_share_verification_and_tree_state` with a `context_paths` assertion |
| **Constraint** Production `build_f_tasks` stays correct (no enrichment) | Task 2 leaves `build_f_tasks`/`_task` untouched; `test_production_f_tasks_carry_no_context_paths`; Task 1 `test_build_candidate_tree_missing_context_key_defaults_to_none` |
| **Constraint** No frozen-record / `verify_spec_hash` change | Attach-point decision (above): `compute_spec_hash` never reads `initial_state`; no spec/serialize field added |
| **Constraint** No prompt change; no `arm_id`/spec field; no Factor V executor; no driver; no held-out-oracle change | Scope honored — only `f_candidate.py` + `f_tasks.py` + tests touched |
| **Constraint** TDD / FP house style: pure tree builder + pure predicate | Tasks 1, 3 (both pure; predicate has no I/O) |
| **Constraint** Reuse existing `prefix_collision` — do not reimplement | Task 3 imports `prefix_collision` from `tools/code_world` |
| **Constraint** `ruff check .` AND `ruff format --check .` whole-repo clean; pytest `-o addopts=""` | Task 5 |
| **Constraint** Stage only own files — no broad `git add` | Every commit lists exact paths |

**Placeholder scan:** no TBD/TODO; every code step shows the actual code; every command shows expected output. **Type consistency:** `seeded_held_out_disjoint(seeded_paths: Sequence[str], held_out_files: Mapping[str, str]) -> bool` is referenced identically in Tasks 3 and 4; `context_paths` (tuple[str, ...]) is referenced identically in Tasks 1, 2, 4; `_F1/_F2/_F3_CONTEXT_PATHS` names match between `f_tasks.py` and the test mirrors (`_F1/_F2/_F3_CONTEXT`).

## Spec gaps (judgment calls)

1. **F3 needs no new context paths (§C).** The spec/§C say "F3 tree is already broad — *curate* which tests are visible vs oracle." I audited every seeded `__tests__/*.test.js` and confirmed none asserts the F3 discriminating behavior (cap + skip-when-empty + highlight-only-problem-requests); the `cap`/`summary` substrings are `capture`/`summarizeNetwork`/`MAX_DEPTH`, unrelated. So curation here is *confirmation*, satisfied by `_F3_CONTEXT_PATHS = ()` + the Task 4 assertions, not by adding/removing files. (If a reviewer wants F3 to *narrow* its seeded tests, that is a separate change to `_f3_candidate_tree`'s seed list — out of scope for "enrichment" and would touch the existing green `_f3_candidate_tree` tests.)
2. **F1 siblings vs `BasePage.js` (§C / §11.6).** §C says "the `waitFor*` siblings." Only `LibraryNotification.js` (the target, already seeded) has the explicit `while+retry+throw` poll loop; the canonical `waitForElementVisible({timeout, timeoutMsg})` convention lives in `BasePage.js` (87 KB inherited driver wrappers). I judged BasePage too large and too low-signal (it does not surface the *poll-and-throw* discriminating shape) and chose three small common siblings that exercise the `waitFor*` convention instead — non-vacuous for P, cheap for the tree.
3. **F2 source inclusion is the leak-risk call (§C).** Including `index.js` makes the `{signal, confidence}` shape readable — which is the *intended* enrichment — while the held-out `f2.held_out.test.js` (asserting the `wdio.conf.ts` summary surfaces both) and the two split-asserting unit tests stay excluded. This is the file I most worried might leak; it is safe because §B.5/§11.6 explicitly want the shape *readable from source* while excluding *tests that assert the split*.
