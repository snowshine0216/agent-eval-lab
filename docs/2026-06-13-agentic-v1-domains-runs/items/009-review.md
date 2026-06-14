Verdict: PASS-WITH-NITS

```
Source: tier-2 pre-landing review subagent (sonnet) — substitutes /ship steps 8+9
PR: https://github.com/snowshine0216/agent-eval-lab/pull/19
Findings: 3
  - tests/runners/test_f_run.py:76 — nit — `assert "const diagResult = await analyzeFailure" not in conf` embeds a golden-new symbol name (the F2 fix's key signature) in a tracked test file. It is a NEGATION assertion (confirming the pre-fix base is clean), not a positive leak, and the mandatory integrity grep (`waitForSnapshotFinalNotificationByName|largePromptedDocument|\[DiagTrace\]|signal=<signal>`) produces 0 hits. Risk is low (it is not candidate-visible at task execution time), but it names a golden-new identifier in the public repo — borderline Leak B pattern. Acceptable as-is; document or extend the integrity grep to cover `diagResult` in future passes.
  - src/agent_eval_lab/datasets/f1_oracle.py:20-21, f2_oracle.py:15-16, f3_oracle.py:21-22 — nit — `WDIO_PKG_REL` and `WDIO_PKG_CONTENT` are defined identically in all three oracle files. DRY violation; extract to a shared `wdio_constants.py` or import from `f3_oracle`. No correctness impact since values are identical.
  - src/agent_eval_lab/runners/f_run.py:37-43 — nit — `prefix_candidate_tree` calls `subprocess.run(..., check=True)` with no try/except. A missing `f_repo` path or bad SHA raises `CalledProcessError` uncaught, crashing the entire F branch rather than yielding a graded-FAIL outcome. Consistent with D-domain's "let it crash" style, but worth noting for resilience; no test covers the missing-repo path.
Integrity (golden tokens in tracked files): 0 — clean (git grep -nE "waitForSnapshotFinalNotificationByName|largePromptedDocument|\[DiagTrace\]|signal=<signal>" -- src tests produces no output)
Oracle soundness (behavioral, not token-grep): confirmed — F1 extracts `waitForSnapshotFinalNotificationByName` method body and executes it with injected fakes (terminal-state matrix); F2 extracts and executes the `[DiagTrace]` block with injected logger/snapshotFn/diagResult; both require live behavioral execution, so a token-only mutant (structurally present but logically wrong) would be caught by the injected-fake tests. F3 mirrors the same pattern (established in prior item 004). Mutant fixtures are read from gitignored `evaluator-only/web-dossier-golden/mutants/` at grade time; no mutant find/replace strings are inlined in tracked files.
```

## Detail notes

**FP discipline:** `build_f1_verification`, `build_f2_verification`, `build_f3_verification` are pure (Path → AllOf, no side effects beyond file read). `build_f_tasks` is pure. `run_f` is a pure iterator that delegates side effects to the injectable `build_tree_fn`. `prefix_candidate_tree` has a subprocess side effect (read-only `git show`) which is appropriate at the I/O edge. All functions are small (< 40 lines), no shared mutable state, no arg mutation. `_grade_tree` builds a fresh `Trajectory`/`RunResult` each call. Mirrors `f3_oracle` style correctly.

**F-domain wiring:** `_load_m1_domain_tasks` wires `build_f_tasks(evaluator_store=store / "web-dossier-golden")` → `{"D": tasks, "F": f_tasks}`. `run_m1` gates the F branch on `f_tasks and f_repo is not None`. The `_build_tree` closure captures `f_repo` (function-level parameter, not a loop variable) — no closure-staleness bug; `tuple(run_f(...))` forces eager evaluation within the loop body. The `evaluator_store` passed to `run_m1` (the plain `store` root) is not used for F grading — F verification content is baked into the task object at build time.

**Store subdir consistency:** `cli.py:822` passes `store / "web-dossier-golden"` as `evaluator_store` to `build_f_tasks`; each oracle then reads `evaluator_store / "golden-files/fN.held_out.test.js"`. The actual gitignored path is `evaluator-only/web-dossier-golden/golden-files/` — consistent.

**Edge cases:** Empty `tasks` → `run_f` yields nothing (correct). `f_repo=None` in `run_m1` → F branch silently skipped (correct). `k=0` → `runs = ()` and `attempts = ()`, `ReplacementOutcome(valid_runs=(), attempts=(), void=False)` — structurally valid, though callers upstream of run_m1 are assumed to enforce `k >= 1`.
