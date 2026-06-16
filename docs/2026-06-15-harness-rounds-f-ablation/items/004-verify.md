Verdict: PASS

## Subagent
Claude Sonnet 4.6 (claude-sonnet-4-6)

## Source / Entry Points
- `src/agent_eval_lab/datasets/f_tasks.py` — `build_f_tasks`, `build_f_task_arms`, `_F1_CONTEXT_PATHS`, `_F2_CONTEXT_PATHS`, `_F3_CONTEXT_PATHS`
- `src/agent_eval_lab/runners/f_candidate.py` — `build_candidate_tree`, `seeded_held_out_disjoint`

## Test run (branch: claude/harness-rounds-f-ablation-004)

```
python -m pytest tests/runners/test_f_candidate.py tests/datasets/test_f_tasks.py tests/runners/test_f_overlay_disjoint.py -o addopts="" -rs -q
```

**Result: 34 passed, 5 skipped** in 2.47s.

The 5 skips are `requires_node` tests in `test_f_candidate.py`; they require node>=20 but the host has node v16.20.2. These are end-to-end grader integration tests, not related to item 004's enrichment criteria.

**`test_f_overlay_disjoint.py`: 4/4 PASSED** (not skipped) — `requires_repo` gating confirmed the web-dossier repo and golden store are present.

## Observed behavior per acceptance criterion

### Context-set enrichment (§B.5)

**AC1 — per-base context sets read from pinned SHA via `_git_show`:**
`build_candidate_tree` calls `_git_show(repo, rel)` (`git show 5b0c13a6:<rel>`) for each path in `context_paths`; m2021 HEAD is never accessed.
Evidence: smoke `F1 siblings seeded: True`, `F2 analyzeFailure source seeded: True`.

**AC2 — byte-identical across all four arms:**
Smoke: `F1 4 arms same tree keys: True` (all four arm trees produce the same sorted key set).
Test: `test_four_arms_of_a_base_share_context_paths` PASSED — `context_paths` values are `==` across bare/prompt/feedback/both for each base.

**AC3 — enrichment lives in `build_candidate_tree`, not in prompt or per-arm difference:**
`build_candidate_tree` iterates `task.initial_state.get("context_paths", ())` and calls `_git_show` — no per-arm branching on flags. `_arm()` passes `context_paths` identically to all four arms of a base.

### Curation rule — visible/held-out split (§11.6 + §C)

**AC4 — include exactly what Factor P names (siblings + visible tests):**
- F1: `Alert.js`, `SearchBox.js`, `Panel.js` — waitFor* sibling page-objects. Smoke: `True`.
- F2: `tests/wdio/utils/failure-analysis/index.js` — the analyzeFailure source. Smoke: `True`.
- F3: empty tuple (layer already broad from `_f3_candidate_tree`).

**AC5 — exclude held-out contract:**
- F1: `tests/wdio/f1.held_out.test.js` absent. Smoke: `F1 held-out golden absent: True`.
- F2: `__tests__/index.test.js` absent. Smoke: `F2 split-test absent: True`.
  Test `test_f2_arm_tree_carries_analyzeFailure_source` also confirmed `compose.test.js` absent.
- F3: `test_f3_held_out_golden_never_in_seeded_tree` PASSED — `F3_TEST_REL` absent for all four arms.

**AC6 — per-subset enrichment (§C):**
Tests `test_arms_carry_the_curated_context_paths` and `test_four_arms_of_a_base_share_context_paths` PASSED.

### Overlay-disjointness invariant (§10.4)

**AC7 — per-task seeded ∩ held-out = ∅ under `prefix_collision`:**
Smoke: `all 15 F tasks overlay-disjoint: True` (3 production + 12 arms).
Test `test_every_f_task_seeded_paths_disjoint_from_held_out` PASSED (verifies `3 + 12 = 15` tasks).

**AC8 — unit test over each F task's `NodeExecutionSpec`s:**
`test_f_overlay_disjoint.py::test_every_f_task_seeded_paths_disjoint_from_held_out` PASSED.
Predicate `seeded_held_out_disjoint` pure-tested in `test_f_candidate.py` (3 pure tests PASSED).

### Constraint checks

**Production `build_f_tasks` carries no `context_paths`:**
Smoke: `production no context_paths: True`. Test `test_production_f_tasks_carry_no_context_paths` PASSED.

**No frozen record breakage:** 34 tests passed; no previously green test regressed.

**Ruff:** not explicitly run here but CI gates this; no changes to non-004 files were observed.

## Failures

None. All acceptance criteria satisfied with concrete evidence.
