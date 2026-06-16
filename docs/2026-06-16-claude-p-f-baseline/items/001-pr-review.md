Verdict: PASS-WITH-NITS

Source: /code-review on PR #38
PR comment URL: https://github.com/snowshine0216/agent-eval-lab/pull/38#issuecomment-4717717880
Findings: 2
  - cli.py:1475-1478 — nit — `_real_claude_factory` calls `tempfile.mkdtemp()` for both workdir and clean-home on every attempt but never cleans up; a full 30-run leaves 360 temp dirs on disk. Non-blocking (OS cleans on reboot, no sensitive data), but worth noting.
  - cli.py:1464 — nit — `factory(*, model, surface, condition_id)` accepts `condition_id` but never uses it (not forwarded to `make_claude_run_fn`; condition is embedded in `RunResult` by `run_f_candidate`). Dead parameter could confuse future readers.

Known / deferred (from 001-review.md — not re-raised as new findings):
  - `is_error` → env-invalid may mask budget-exhausted model misses — methodology decision, deferred to owner.
  - `--smoke` silently overrides `--surface`/`--bases`/`--k` — documented behavior.

Verified clean:
  - No shell-injection surface (subprocess.run(list), no shell=True).
  - _sanitized_env correctly strips contaminating keys, preserves auth/PATH/HOME.
  - summarize_baseline math correct (zip strict=True, n_valid=0 guarded, k=0 → void).
  - read_back_tree ignore filter uses exact top-level parts[0] (no substring false-positives).
  - All 5 env-invalid degradation paths tested (timeout, nonzero-exit, parse-error, is_error, non-UTF-8 read-back).
  - _append_runs writes all attempts (intentional for drill-down; test confirms).

## Fix-loop resolution (commit d903f10) — both nits resolved + verify-surfaced defect fixed

- **nit cli.py:1475-1478 (temp-dir leak) → FIXED:** `run_fn` now removes its `workdir` + `clean_home` in a `finally` (read-back happens first, so the produced tree is already in memory). Test `test_run_fn_cleans_up_workdir_and_home`.
- **nit cli.py:1464 (dead `condition_id`) → FIXED:** parameter dropped from `_real_claude_factory`'s inner `factory` and the call site.
- **verify-surfaced defect (NOT a nit): `python -m agent_eval_lab` was broken repo-wide** (no `__main__.py` / no console script) — the documented Task 7 / owner smoke recipe and every agentic recipe would fail with "No module named agent_eval_lab.__main__". FIXED: added `src/agent_eval_lab/__main__.py`; test `test_python_m_entrypoint_help_works`; confirmed `python -m agent_eval_lab run-f-claude-baseline --smoke --dry-run` exits 0. Post-fix full suite green, ruff clean.
