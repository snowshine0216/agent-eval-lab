# Item 004 — Candidate-tree enrichment + visible/held-out curation

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override). Authoritative source: **§B.5** (context-set enrichment), **§10.4** (overlay-disjointness
> invariant + unit test), **§11.6** (curation rule), **§C** (per-subset F1/F2/F3 enrichment), and
> **Part G step 4**. Builds on item 003 (the 12 task-arms share byte-identical `initial_state`).

## Goal

Make Factor P's directives **non-vacuous** and give Factor V **real siblings/tests to learn from**
by enriching each F base task's candidate tree with a curated **context set** materialized
**identically across all four arms** from the pinned base SHA (`5b0c13a6`, D32; m2021 HEAD never
read). Today F1/F2 candidate trees contain only `target_paths` + a minimal `package.json`
([f_run.py prefix_candidate_tree](../../../src/agent_eval_lab/runners/f_run.py)), so P's "read the
siblings / read the visible tests" directives reference context that **isn't present** (§B.3). The
enrichment must respect a **visible/held-out split** that never reveals the discriminating contract,
and a per-task **overlay-disjointness invariant** so enrichment cannot collide with the held-out node
oracle's grade-time overlay.

## Acceptance criteria

**Context-set enrichment (§B.5):**
- [ ] Per F base task, define a **context set** — additional seeded paths beyond `target_paths`,
  read from the pinned base SHA via `git show 5b0c13a6:<path>` (never a checkout, never m2021 HEAD).
- [ ] The enriched tree is materialized **identically (byte-for-byte) across all four arms** of a
  base. (003's invariant: arms share `initial_state`; enrichment must preserve that — `bare`/
  `prompt`/`feedback`/`both` of one base get the same tree, so the tree cannot confound P or V.)
- [ ] Enrichment lives in the candidate-tree-building path (e.g. extend `build_candidate_tree` /
  the per-task context-path source) — **not** in the prompt and **not** in a per-arm difference.

**Curation rule — visible/held-out split (§11.6 + §C):**
- [ ] **Include exactly what Factor P names:** the **sibling modules** in the edit target's layer,
  the **local conventions** file if the layer has one (README/config/nearest convention), and the
  **visible tests** that exercise the contract.
- [ ] **Exclude anything that reveals the held-out contract:** the **oracle/golden tests** (D19) and
  **any visible test asserting the *discriminating* behavior** — F1 the throw-on-timeout, F2 the
  two-field `result.signal`+`result.confidence` split, F3 the cap+summary. The visible/oracle split
  mirrors the shallow-vs-deep contract gradient the failure analysis found.
- [ ] **Per-subset enrichment (§C)** — the plan enumerates the concrete files from the local repo at
  the pinned SHA:
  - **F1** (`LibraryNotification.js` + spec): include the `waitFor*` **sibling page-objects** in
    `tests/wdio/pageObjects/common/` that surface the poll/timeout/throw pattern + the spec that
    calls the helper. Exclude the held-out throw-path golden test.
  - **F2** (`wdio.conf.ts`): include `analyzeFailure`'s **source** (in `tests/wdio/utils/
    failure-analysis/`) so its return shape (`signal`/`confidence`) is **readable from the source**,
    while excluding any visible test that *asserts* the two-field split.
  - **F3** (`report-to-allure.js`): tree is **already broad** (the F3 oracle seeds the
    `failure-analysis` causal layer minus `F3_TEST_REL`, [f3_oracle.py](../../../src/agent_eval_lab/datasets/f3_oracle.py)).
    **Curate** which of its tests are visible vs oracle — confirm the cap+summary golden stays
    held-out; do not newly reveal the discriminating behavior.

**Overlay-disjointness invariant (§10.4) — REQUIRED:**
- [ ] Per F task, assert that **every seeded (visible) path is disjoint under `prefix_collision`
  from that task's `held_out_files`**, and that enrichment **never adds a path the oracle overlays/
  displaces**. The held-out node oracle overlays its golden test into the candidate tree at grade
  time; `overlay_node_oracle` raises `NodeOverlayCollision` → `tree_collision` error
  ([node_oracle_edge.py](../../../src/agent_eval_lab/runners/node_oracle_edge.py)) if a seeded path
  collides with a held-out path. A silent collision would turn an arm's runs into
  `agent_failure / tree_collision`, polluting the very comparison the enrichment serves.
- [ ] Enforce the invariant with a **unit test over each F task's `NodeExecutionSpec(s)`** — for
  every base (and its arms), assert seeded paths ∩ held-out paths = ∅ under `prefix_collision`. The
  test must fail if a future enrichment introduces a colliding path.

## Non-goals (deferred / out of run scope)
- **Factor V executor + sandbox (item 005).** No `sandboxed_node_edge.py`, no executor.
- **Driver / `f_ablation_spec` / seeded order (item 006).** No execution.
- **No change to the held-out oracles or golden tests** (D19 — frozen; their bytes are the grade
  contract). 004 curates the *visible* (candidate-seeded) side only.
- **No `arm_id`/`ArmDef`/`ConditionDef`/`ExperimentSpec`/serialize change** (003 already established
  arm-as-task; 004 only changes which files are seeded). Frozen M1 specs must keep verifying.
- **No prompt change** (Factor P block is item 003 — done).
- **No paid provider execution.**

## Constraints
- **Reads only the pinned base SHA** (`5b0c13a6`) from the local web-dossier repo
  (`~/Documents/Repository/web-dossier`); m2021 HEAD never read. The repo is present locally so the
  context set is concretely enumerable offline.
- **Preserve 003's byte-identical-tree invariant**: the four arms of a base must still get the same
  enriched tree. Add/extend a test asserting this if 003's test doesn't already cover the enriched
  paths.
- **Production `build_f_tasks` path stays correct**: the un-armed production F tasks (used by
  `m1_spec`) keep their minimal trees unless the design intends them enriched too — the **enrichment
  is for the ablation arms** (40-round, exploratory). The plan decides whether enrichment attaches to
  the base task (shared by both builders) or only to `build_f_task_arms`; either way it must not
  break the existing `prefix_candidate_tree` / `_f3_candidate_tree` tests or change frozen records.
- **TDD / FP house style**: pure tree-builder functions; the overlay-disjointness check is a pure
  predicate over `(seeded_paths, held_out_files)`.
- **Stage only own files — NO broad `git add`** (security lesson from item 002).
- CI runs `ruff check .` AND `ruff format --check .` over the whole repo — keep both clean. Run
  pytest with `-o addopts=""` to see counts.
- No network. Offline TDD only.
