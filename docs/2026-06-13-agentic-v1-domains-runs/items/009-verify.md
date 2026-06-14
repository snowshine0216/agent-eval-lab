Verdict: PASS
Subagent: sonnet
Source: /verify fallback — F-oracle discrimination + wiring (round 2, post-fix e5f7ad3)
Entry point exercised:
  uv run pytest tests/datasets/test_f1_oracle.py tests/datasets/test_f2_oracle.py -q -p no:cacheprovider
  uv run pytest tests/datasets/test_f_tasks.py tests/runners/test_f_run.py tests/experiments/test_m1_run.py -q -p no:cacheprovider
  git grep -nE "analyzeFailure|diagResult|\[DiagTrace\]" -- src tests

Observed behavior:
  - F1 discriminates — test_build_f1_does_not_leak_golden_source_into_held_out PASS,
    test_f1_passes_golden_fails_prefix_and_mutants PASS; oracle confirms golden PASS /
    5b0c13a6 prefix FAIL / mutants ('keeps-image-compare', 'error-path-gutted') FAIL;
    5 passed in 0.72s (combined with F2)
  - F2 discriminates + var-name-agnostic capture PASSes —
    test_build_f2_does_not_leak_golden_source_into_held_out PASS,
    test_f2_passes_golden_fails_prefix_and_mutants PASS (golden PASS / prefix FAIL /
    mutants 'surfaces-2xx'+'omits-signal-line' FAIL),
    test_f2_passes_when_capture_variable_name_is_not_the_golden_name PASS (oracle grades
    True when capture var renamed to alt identifier; anchors on pattern not specific name);
    5 passed in 0.72s
  - F task builder + run-m1 F wiring intact —
    test_build_f_tasks_returns_three_node_oracle_tasks PASS,
    test_f_tasks_carry_the_repo_relative_target_paths PASS,
    test_run_f_yields_one_outcome_per_task_with_stubbed_tree PASS,
    test_run_f_golden_tree_passes_f1 PASS,
    test_prefix_candidate_tree_pins_5b0c13a6_not_head PASS (CANDIDATE_BASE_SHA dedup
    intact),
    test_run_m1_threads_dset_per_condition PASS,
    test_run_m1_f_branch_yields_outcomes PASS,
    test_run_m1_skips_absent_domains_without_crashing PASS;
    8 passed in 0.44s
  - no-leak (git grep 0) — git grep -nE "analyzeFailure|diagResult|\[DiagTrace\]" -- src tests
    returned 0 matches (exit 1 = no hits); leak-A/B fixes da37f94/cb86914 hold
Failures: none
