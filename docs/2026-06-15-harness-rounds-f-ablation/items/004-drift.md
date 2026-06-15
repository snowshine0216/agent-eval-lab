Verdict: PASS

Subagent: sonnet / Plan checklist items: 5 tasks × multiple steps / Verified present in diff: all 5 tasks fully implemented

## Plan checklist vs diff

### Task 1 — `context_paths` enrichment in `build_candidate_tree` (OK)

All three unit tests from the plan are present verbatim in `tests/runners/test_f_candidate.py`:
- `test_build_candidate_tree_seeds_context_paths` (monkeypatching `_git_show` + `fr.subprocess.run`)
- `test_build_candidate_tree_empty_context_paths_is_minimal`
- `test_build_candidate_tree_missing_context_key_defaults_to_none`

Implementation in `src/agent_eval_lab/runners/f_candidate.py` matches the plan exactly:
```python
tree = dict(prefix_candidate_tree(task, repo=repo))
for rel in (task.initial_state or {}).get("context_paths", ()):
    tree[rel] = _git_show(repo, rel)
return tree
```
F3 path check (`task.id == "f-f3" or task.id.startswith("f-f3-")`) precedes enrichment, unchanged.

### Task 2 — Per-base `context_paths` on ablation arms (OK)

`_F1_CONTEXT_PATHS`, `_F2_CONTEXT_PATHS`, `_F3_CONTEXT_PATHS` constants added to
`src/agent_eval_lab/datasets/f_tasks.py` after the `_F3_USER` block (around line 58 per plan),
with the exact three F1 siblings, the single F2 source, and an empty tuple for F3.

`_arm` signature extended with `context_paths: tuple[str, ...]` and threaded into `initial_state`.
`build_f_task_arms` bases tuple expanded from 4-tuples to 5-tuples carrying context_paths; destructuring
updated in the comprehension. `build_f_tasks` and `_task` left untouched — confirmed via inspection
(`src/agent_eval_lab/datasets/f_tasks.py` lines 100–193 in the final file show `_task` and
`build_f_tasks` carry no `context_paths`).

Test additions in `tests/datasets/test_f_tasks.py`:
- `test_arms_carry_the_curated_context_paths` — all 12 arms checked (OK)
- `test_four_arms_of_a_base_share_context_paths` — byte-identical per base (OK)
- `test_production_f_tasks_carry_no_context_paths` (OK)
- The existing `test_four_arms_of_a_base_share_verification_and_tree_state` extended with
  `t.initial_state["context_paths"] == ref.initial_state["context_paths"]` assertion (OK)

### Task 3 — `seeded_held_out_disjoint` predicate (OK)

`prefix_collision` imported from `agent_eval_lab.tools.code_world` at `f_candidate.py` — confirmed
by diff line showing it added to the existing import block. No reimplementation.
`seeded_held_out_disjoint` placed directly below `build_candidate_tree`, uses `not any(prefix_collision(...))`.
`Sequence` and `Mapping` types were already available via `from collections.abc import ..., Mapping, Sequence`
(line 21 in final file).

All three predicate unit tests present and matching plan exactly:
- `test_seeded_held_out_disjoint_true_for_disjoint_paths`
- `test_seeded_held_out_disjoint_allows_identical_displaced_path`
- `test_seeded_held_out_disjoint_false_on_canonical_prefix_collision`

### Task 4 — §10.4 invariant test (OK)

`tests/runners/test_f_overlay_disjoint.py` created as a new file. All four tests match the plan:
- `test_every_f_task_seeded_paths_disjoint_from_held_out` — asserts 3+12 tasks, all specs checked
- `test_f3_held_out_golden_never_in_seeded_tree`
- `test_f1_arm_tree_carries_the_curated_siblings`
- `test_f2_arm_tree_carries_analyzeFailure_source`

The `requires_repo` mark correctly guards on `_REPO.exists()` and golden-file presence.

### Task 5 — Whole-repo verification (OK)

Evidenced by the separate `chore(004): ruff lint + format fixes (import sort, line length)` commit
(`a8c1ec5`), which corrected import ordering and line length in `f_candidate.py`, `test_f_tasks.py`,
and `test_f_overlay_disjoint.py`. The fix commit confirms lint/format was run and the repo is clean.

## Scope boundary checks

All five scope constraints held:

1. **`context_paths` only on arm `initial_state`, not production `build_f_tasks`/_task** — confirmed:
   `_task` (lines 100–125) has no `context_paths`; `build_f_tasks` passes only `target_paths`.

2. **Concrete context paths match plan exactly**:
   - F1: `Alert.js`, `SearchBox.js`, `Panel.js` (all in `tests/wdio/pageObjects/common/`) ✓
   - F2: `tests/wdio/utils/failure-analysis/index.js` ✓
   - F3: `()` ✓

3. **`seeded_held_out_disjoint` reuses `prefix_collision`** (imported, not reimplemented) ✓

4. **No item 005/006 scope creep** — grep for `arm_id`, `ConditionDef`, `ExperimentSpec`,
   `serialize`, `executor`, `driver` in the diff returns only the existing docstring
   mention "no arm_id" (unchanged text). ✓

5. **No held-out oracle/golden file changes** — `git diff … -- '*oracle*' '*golden*' '*held_out*'`
   returns empty. ✓

6. **"Make it bite" revert** — no case-variant colliding path (`F1.held_out.test.js` or similar)
   in the final `f_tasks.py`. The file contains only the canonical three F1 siblings. ✓

## §10.4 "bite" methodology assessment

**NOTE (not a blocker).** The plan's Task 4 Step 3 intended a case-variant path
(e.g. `"tests/wdio/F1.held_out.test.js"`) added temporarily to `_F1_CONTEXT_PATHS`, then
`test_every_f_task_seeded_paths_disjoint_from_held_out` re-run against the live repo. As the plan
itself acknowledges, that path does not exist at SHA `5b0c13a6`, so `_git_show` / `git show` would
have exited 128 before `seeded_held_out_disjoint` could be reached — the test would have failed via
a subprocess error, not via the disjointness assertion.

However, the disjointness predicate's own unit test
`test_seeded_held_out_disjoint_false_on_canonical_prefix_collision` in `test_f_candidate.py`
*does* genuinely prove the predicate bites: it passes `("tests/wdio/Foo.js",)` as `seeded_paths`
against `{"tests/wdio/foo.js/held.test.js": "x"}` as `held_out_files`. `prefix_collision` returns
`True` at segment depth 2 (raw `tests/wdio/Foo.js` vs `tests/wdio/foo.js` differ but canonically
match), so `seeded_held_out_disjoint` correctly returns `False`. The predicate is proven to fail on
a real canonical-case collision entirely independently of any repository path existence. The
invariant test `test_every_f_task_seeded_paths_disjoint_from_held_out` then correctly chains the
proven predicate over all 15 tasks. Classified as NOTE only — the predicate correctness is
adequately proven via the dedicated unit test; the bite-check's methodology diverged from the plan
but the result is sound.

## Drift findings

None. Zero unimplemented plan items, zero divergences, zero scope creep.

Changed files: `src/agent_eval_lab/datasets/f_tasks.py`,
`src/agent_eval_lab/runners/f_candidate.py`,
`tests/datasets/test_f_tasks.py`,
`tests/runners/test_f_candidate.py`,
`tests/runners/test_f_overlay_disjoint.py` (new),
`docs/2026-06-15-harness-rounds-f-ablation/PROGRESS.md` (chore, incidental).
