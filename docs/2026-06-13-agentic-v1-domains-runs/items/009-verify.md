Verdict: PASS
Subagent: sonnet
Source: /verify fallback — F-oracle discrimination + run-m1 wiring (deterministic, env-free)
Entry point exercised:
  uv run pytest tests/datasets/test_f1_oracle.py -v -p no:cacheprovider
  uv run pytest tests/datasets/test_f2_oracle.py -v -p no:cacheprovider
  uv run pytest tests/datasets/test_f_tasks.py tests/runners/test_f_run.py tests/experiments/test_m1_run.py tests/test_cli.py -v -p no:cacheprovider
  git grep -nE "waitForSnapshotFinalNotificationByName|\[DiagTrace\]" -- src tests

Observed behavior:
  - F1 oracle discriminates (golden PASS / prefix FAIL / 2 mutants FAIL) — test_build_f1_does_not_leak_golden_source_into_held_out PASS, test_f1_passes_golden_fails_prefix_and_mutants PASS; the composite test asserts golden PASS, 5b0c13a6 prefix FAIL, and both mutants ('keeps-image-compare', 'error-path-gutted') FAIL; 2 passed in 0.38s (no skips; node>=20 + golden store present; all mutants confirmed non-no-op)
  - F2 oracle discriminates (golden PASS / prefix FAIL / 2 mutants FAIL) — test_build_f2_does_not_leak_golden_source_into_held_out PASS, test_f2_passes_golden_fails_prefix_and_mutants PASS; mutants ('surfaces-2xx', 'omits-signal-line') both FAIL; 2 passed in 0.35s
  - run-m1 F branch + cli F-loading — test_run_m1_f_branch_yields_outcomes PASS (run_f stubbed, yields ReplacementOutcome with grade.passed=True); test_load_m1_domain_tasks_includes_f PASS (domain_tasks["F"] == ["f-f1","f-f2","f-f3"]); test_run_f_yields_one_outcome_per_task_with_stubbed_tree PASS; test_run_f_golden_tree_passes_f1 PASS; test_prefix_candidate_tree_pins_5b0c13a6_not_head PASS; test_build_f_tasks_returns_three_node_oracle_tasks PASS; 45 passed in 6.79s across all 4 files
  - no-leak (golden only in gitignored evaluator-only) — git grep returned 0 matches; evaluator-only/ confirmed gitignored (.gitignore:16:/evaluator-only/); golden-files/ and mutants/ present locally only; F1_SPEC_REL/F1_PAGE_REL/F2_CONF_REL confirmed absent from held_out_files in the oracle
Failures: none
