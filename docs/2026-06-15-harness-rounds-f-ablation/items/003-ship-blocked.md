# 003 — /ship steps 8+9 review: blockers found (pre-push)

Source: /ship steps 8 (pr-review-toolkit:code-reviewer + silent-failure-hunter) + 9 (adversarial).
Verdict before fixes: **FAIL** — 1 latent P0 + CI-red lint. Routed through a pre-push fix round
(ship.md "/ship review can demand fixes before push"). After fixes → re-review → re-ship.

## Blockers (must fix before push)

### B1 — Latent P0: `build_candidate_tree` F3 dispatch doesn't match arm ids (adversarial: BREAKS)
[f_candidate.py:124](../../../src/agent_eval_lab/runners/f_candidate.py:124) dispatches on
`if task.id == "f-f3"`. Item 003 renamed the F3 task to four armed ids (`f-f3-bare`, `f-f3-prompt`,
`f-f3-feedback`, `f-f3-both`) — **none match** the exact string, so every F3 arm falls through to
`prefix_candidate_tree`, missing the `failure-analysis/` causal layer the held-out guard tests
import. Latent (no driver runs arms in 003) but bites in 004/005/006: all 4 F3 arms would silently
get an under-seeded workspace → oracle guard tests fail at grade → all F3 arms score 0 regardless of
edit quality (corrupt ablation data). **003 introduced the id change, so 003 fixes the dispatch.**
Fix: match `task.id == "f-f3" or task.id.startswith("f-f3-")` (and confirm F1/F2 arms correctly route
to `prefix_candidate_tree` — they are self-contained in `target_paths`, no special dispatch). Add a
unit test that `build_candidate_tree` for `f-f3-bare` includes the causal layer (mirror the existing
`test_build_candidate_tree_f3_includes_causal_layer_minus_held_out`, which only covered the un-armed
`f-f3` and masked this regression).

### B2 — CI blocker: `ruff check .` fails on the new test files
CI runs `uv run ruff check .` ([ci.yml:17](../../../.github/workflows/ci.yml)). The new 003 tests
trip 5 lint errors the impl only checked `ruff format` (not `ruff check`) on the test files:
- `E501` long comment — [test_f_candidate.py:173](../../../tests/runners/test_f_candidate.py:173)
- `I001` un-sorted function-local import blocks ×4 (httpx third-party must precede first-party
  `agent_eval_lab` imports) in the run_uid / collision / V-guard / bare-prompt tests.
Fix: `ruff check --fix` for the I001s, manually wrap the long comment, then confirm
`ruff check .` and `ruff format --check .` both clean over the WHOLE repo.

## Cheap quality fixes (fold into the same round)

### Q1 — dead `paths_key` loop var — [test_f_tasks.py:42](../../../tests/datasets/test_f_tasks.py:42)
`for base, paths_key in (("f1", None), …)` never uses `paths_key`. Simplify to
`for base in ("f1", "f2", "f3"):`.

### Q2 — strengthen verification-identity assertion — [test_f_tasks.py:48](../../../tests/datasets/test_f_tasks.py:48)
Comment says "SAME object (identity)" but asserts `==`. The four arms DO share one object
(`build_fN_verification` called once per base), so tighten to `assert t.verification is ref.verification`.

## Not a bug (documented, no code change)
- Silent-failure-hunter "missing factor_v silently runs as bare": the missing-key→bare default is
  **intentional** — un-armed production tasks (`build_f_tasks`) carry no factor flags and must run as
  bare. The only producer of armed tasks (`build_f_task_arms`) always sets both flags, and tasks are
  built fresh by the driver (no initial_state rehydration into runs). So missing-flag-means-bare is
  correct, not a silent degradation. No defensive assertion added (it would break un-armed tasks).
- Code-reviewer P1 "edit_task reused across k runs shares initial_state['files']": pre-existing (not
  introduced by 003); `code_world.apply` is purely functional (returns new dicts, never mutates), so
  no aliasing bug. Out of 003 scope; noted for a possible follow-up.
