# 009 — F-domain repo adapter (F1/F2) spec

Spec status: **⏭️ pre-completed** — derived from the frozen source spec §4.1/§18.6, decisions
D24/D31/D32, and handoff §5. Brainstorm + grill were completed upstream (3 review rounds + the
2026-06-13 grill); this file restates the item-level intent for the plan phase. The detailed
oracle construction (exact held-out tests + assertions) is **plan-phase work** — the plan subagent
reads the `.golden` files to derive it.

## Goal
Add a **second domain (F)** to the M1 macro composite: an env-free repo-task adapter over
`web-dossier` (wdio toolchain) with **F1 and F2** golden-discriminating Node oracles, reusing the
already-built **F3 pattern**. Wire F into `run-m1` so the report renders D **and** F. The live
candidate F-runs across the roster are the **post-merge execute phase** (like 008's D run), not
this PR's gate.

## Background (what already exists — reuse, do not rebuild)
- **F3 is built + green:** `datasets/f3_oracle.py` (`build_f3_verification` → `AllOf` of
  `NodeExecutionSpec`s), `runners/node_oracle_edge.py`, `runners/node_edge.py`,
  `graders/node_execution.py`. The candidate's produced files live in
  `trajectory.final_state["files"]`; the oracle overlays a **held-out golden TEST** onto that tree
  and runs `node --test`. Mirror this shape for F1/F2.
- **Golden (evaluator-only, staged, gitignored):** `evaluator-only/web-dossier-golden/` —
  `meta.json` (candidate_base_sha `5b0c13a6…`, golden_head `ebdfcbea…`, PR #23483, base_ref
  `m2021`), `golden-files/*.golden` (`Snapshots_SendBackground.spec.js`, `LibraryNotification.js`,
  `wdio.conf.ts`, `report-to-allure.js`, `report-to-allure.test.js`), `F-golden.patch`.
- **Candidate repo:** `~/Documents/Repository/web-dossier` (wdio at `tests/wdio`), pinned to the
  frozen pre-fix SHA `5b0c13a6`.

## F1 / F2 oracle targets (source §4.1)
- **F1 — replace flaky image comparison with assertions in `TC99396_10`.** Golden touches
  `Snapshots_SendBackground.spec.js` (image-compare call removed, −7) and adds notification-section
  assertions in `pageObjects/common/LibraryNotification.js` (+16). *Oracle:* the case **no longer
  calls image-compare** AND asserts on **specific owner-specified notification-section content**
  (not "an assertion exists"). **Structural-only checks are rejected (D24).**
- **F2 — diagnose trace on assertion failure.** Golden enhances the wdio fixture in `wdio.conf.ts`
  (+22; the `afterTest`/`afterHook` failure-analysis path). *Oracle:* a **forced-failure harness**
  asserts a diagnose trace of the **owner-specified shape** is produced; reconciled with the
  existing `failure-analysis` engine.

## Acceptance criteria (independently verifiable)
1. **F1 oracle is golden-discriminating:** golden source ⇒ PASS; the pre-fix `5b0c13a6` tree ⇒ FAIL;
   a contradiction-mutant (e.g. keeps image-compare, or weakens the notification assertion) ⇒ FAIL.
   Has ≥ the negative checks the F3 oracle carries. Rejects structural-only solutions.
2. **F2 oracle is golden-discriminating:** golden ⇒ PASS; pre-fix `5b0c13a6` ⇒ FAIL; a
   contradiction-mutant (trace not produced / wrong shape) ⇒ FAIL. Reconciled with the
   `failure-analysis` engine (engine tests stay green).
3. **F wired into `run-m1`:** `cli._load_m1_domain_tasks` (currently returns only `{"D": tasks}`)
   plus `experiments/m1_run.run_m1` (currently skips F/B) gain an **F-domain runner** (candidate
   attempts the repo task → produces a file tree → node oracle grades) and a `build_f_tasks(...)`.
   The report engine already handles F (Clopper–Pearson, 3 tasks) — it renders "not yet run" until
   F outcomes arrive, and renders real F numbers once they do.
4. **TDD throughout** (red→green→refactor); whole-tree ruff clean; full suite green (the known
   oracle-subprocess timeout flakes excepted, guarded as in CI).
5. **No regression** to F3, D, the report engine, or the 008 runner hardening.

## Non-goals
- B-domain / M2 (that's 010).
- The **live candidate F-runs** across the roster + the D+F report regeneration (post-merge execute
  phase, mirroring 008's D run).
- F-domain task-def pre-registration hashing beyond what wiring F into the frozen M1 spec requires
  (handled minimally; full F pre-registration is a separate concern).

## Constraints / integrity (repo is PUBLIC — never relax)
- **Env-free:** F1/F2 grade via `node --test` over held-out tests overlaid on the candidate's
  produced tree — no live infrastructure, deterministic, `pass^k`-valid unconditionally.
- **Candidate pin (D32):** the candidate workspace checks out `5b0c13a6` — **never** `m2021` HEAD
  (once the PR merges, tracking m2021 would leak the answer). No access to the PR/head ref/token.
- **Golden isolation (D19/D33):** golden source/test/object never reachable from any
  candidate-visible location, ref, prompt, or account. Held-out oracle files come from the
  gitignored `evaluator-only/web-dossier-golden/` store at grade time only.
- **D24:** oracles are committed, owner-reviewed; structural-only solutions rejected; negative +
  contradiction checks mandatory.
- Reuse the F3 pattern (`NodeExecutionSpec`/`AllOf`/`node_edge`) — do not invent a parallel runner.

## Resolved decisions (pre-completed — from source spec)
- D31: F is golden-branch-pinned; F1/F2/F3 touch only their owner-specified layers.
- D32: candidate base is the frozen pre-fix SHA, not the open PR's moving base.
- D24: env-free oracles with negative/contradiction checks; no structural-only acceptance.
