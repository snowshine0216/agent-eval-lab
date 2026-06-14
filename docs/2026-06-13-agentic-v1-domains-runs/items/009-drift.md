Verdict: PASS

Subagent: sonnet
Plan checklist items: 7
Verified present in diff: 7

## Plan checklist vs diff

| # | Plan step | Status |
|---|-----------|--------|
| 1 | F1 held-out test (evaluator-only gitignored) + MANIFEST.txt | OK — files are gitignored (evaluator-only); MANIFEST addition confirmed in commit history; per-plan intent satisfied. |
| 2 | `f1_oracle.py` + `tests/datasets/test_f1_oracle.py` | OK — both present in diff; oracle shape matches plan exactly (AllOf/NodeExecutionSpec, held_out_files carries test not source). |
| 3 | `f2_oracle.py` + `tests/datasets/test_f2_oracle.py` | OK — both present; same pattern as F1. |
| 4 | `f_tasks.py` + `tests/datasets/test_f_tasks.py` | OK — `build_f_tasks` returns `(f-f1, f-f2, f-f3)` with correct `initial_state` fields; tests match plan assertions. |
| 5 | `f_run.py` + `run_m1` F branch + `tests/runners/test_f_run.py` + `tests/experiments/test_m1_run.py` F case | OK — `f_run.py` created; `m1_run.py` F branch added; both test files present; `run_f` stubbed in unit test. |
| 6 | `cli._load_m1_domain_tasks` returns `"F"` key + `_run_m1_command` passes `f_repo` | OK — `_load_m1_domain_tasks` returns `{"D": tasks, "F": f_tasks}`; `f_repo` wired into `run_m1` call; `tests/test_cli.py` test added. |
| 7 | Full-suite green + ruff (no new tracked files beyond plan) | OK — diff is additive over precisely the files listed in the plan's File Structure table; no unexpected files. |

## Deviations assessed

- **Task 6 store-path — ACCEPTED.** The plan's literal text read `build_f_tasks(evaluator_store=store)` where `store = Path(cfg.store.path)`. The impl calls `build_f_tasks(evaluator_store=store / "web-dossier-golden")`. This is architecturally correct and necessary: `evaluator.toml` sets `store.path = ".../evaluator-only"`, which is the store root for both D and F artifacts. D's golden files sit directly at that root (`cmc-docs-*.json`); F's sit under `web-dossier-golden/` (a separate subdirectory). Passing the subdirectory to `build_f_tasks` — rather than the root — mirrors the real filesystem layout, prevents `build_f_tasks` from receiving files it must not see, and is consistent with how `build_cmc_tasks` resolves its own golden files relative to its passed root. The corresponding `test_cli.py` test constructs `_Store.path = str(store_root)` (the `evaluator-only` root) and the impl appends `/ "web-dossier-golden"`, confirming the indirection is intentional and tested. Sound.

- **Integrity remediation (da37f94/cb86914) — ACCEPTED; git-grep clean, discrimination preserved.** Post-plan commits (i) removed golden answer tokens (`waitForSnapshotFinalNotificationByName`, `largePromptedDocument`, `[DiagTrace]`) from candidate-visible prompts in `f_tasks.py`, replacing them with paraphrased behavioral descriptions that do not reveal the solution; and (ii) moved the inline mutant find/replace strings out of tracked test files into gitignored `evaluator-only/web-dossier-golden/mutants/*.json`, loaded at test time via `json.loads(_MUTANTS_FILE.read_text(...))`. `git grep -nE "waitForSnapshotFinalNotificationByName|largePromptedDocument|\[DiagTrace\]" -- src tests` returns **zero matches** on this branch. Discrimination is preserved: the tests still load mutants from the gitignored store and assert each must fail; the oracle is behavioral (method extraction + injected fakes) not token-matching, so the absence of literal golden tokens in tracked files does not weaken the grader. These changes improve integrity beyond the plan; the plan's literal prose is superseded.

## Drift findings

None. Every diff hunk maps to a plan step. Incidental additions (imports, docstring updates, format fixups) are cosmetic.

## Integrity (golden tokens in tracked files)

0 — clean. `git grep -nE "waitForSnapshotFinalNotificationByName|largePromptedDocument|\[DiagTrace\]" -- src tests` produces no output on `feat/agentic-v1-009-f-domain`.
