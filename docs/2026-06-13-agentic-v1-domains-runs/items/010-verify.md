Verdict: PASS

Subagent: sonnet
Source: Fallback used: direct pytest/python entry points (library surface, no GUI) — re-run after fix round 1
Entry points exercised:
  - uv run pytest tests/datasets/test_b1_oracle.py -v                              (oracle discrimination)
  - uv run pytest tests/runners/test_b_run.py tests/runners/test_b_isolation.py -v (save-name + isolation)
  - uv run python -c "build_b_tasks(...)" inline snippet                             (M2 arms differ only by skill)
  - uv run pytest tests/experiments/test_m1_run.py tests/experiments/test_evaluator_config_b.py -q
  - uv run pytest -p no:cacheprovider (full suite)
  - uv run ruff check . && uv run ruff format --check .

Observed behavior:

  - Oracle discrimination after fix (F2: order-insensitive grid compare) — all 10 oracle tests:
    ```
    tests/datasets/test_b1_oracle.py::test_golden_correct_readback_passes PASSED
    tests/datasets/test_b1_oracle.py::test_missing_object_fails PASSED
    tests/datasets/test_b1_oracle.py::test_each_failure_mode_fails[wrong_cube] PASSED
    tests/datasets/test_b1_oracle.py::test_each_failure_mode_fails[missing_required_row] PASSED
    tests/datasets/test_b1_oracle.py::test_each_failure_mode_fails[missing_cost_col] PASSED
    tests/datasets/test_b1_oracle.py::test_each_failure_mode_fails[wrong_prompt] PASSED
    tests/datasets/test_b1_oracle.py::test_reordered_data_rows_pass PASSED
    tests/datasets/test_b1_oracle.py::test_wrong_value_in_reordered_rows_still_fails PASSED
    tests/datasets/test_b1_oracle.py::test_grid_matches_helper_empty_grids PASSED
    tests/datasets/test_b1_oracle.py::test_grid_matches_helper_header_order_is_positional PASSED
    10 passed in 0.05s
    ```
    Golden store present locally (evaluator-only/b-set-golden/b1-golden.json + b1-mutants.json).
    All 10 ran (none skipped). Golden correct => PASS; missing object => FAIL; each of
    {wrong_cube, missing_required_row, missing_cost_col, wrong_prompt} => FAIL.
    New reordered-data-rows-correct => PASS (order-insensitive fix works).
    New wrong-value-in-reordered => FAIL (discrimination preserved — fix did NOT make a wrong answer pass).

  - Per-task save-name uniqueness (D20 fix) — all 10 runner tests:
    ```
    tests/runners/test_b_run.py::test_run_b_golden_readback_passes_and_resets PASSED
    tests/runners/test_b_run.py::test_run_b_wrong_cube_readback_fails PASSED
    tests/runners/test_b_run.py::test_run_b_preflight_occupied_name_voids_outcome PASSED
    tests/runners/test_b_run.py::test_two_tasks_under_one_condition_get_distinct_save_names PASSED
    tests/runners/test_b_isolation.py::test_save_name_is_derived_from_run_uid_and_slugged PASSED
    tests/runners/test_b_isolation.py::test_save_name_rejects_empty_run_uid PASSED
    tests/runners/test_b_isolation.py::test_preflight_absent_passes_when_name_is_free PASSED
    tests/runners/test_b_isolation.py::test_preflight_absent_raises_when_name_is_occupied PASSED
    tests/runners/test_b_isolation.py::test_capture_created_id_returns_the_clients_object_id PASSED
    tests/runners/test_b_isolation.py::test_reset_after_grading_deletes_the_captured_object PASSED
    10 passed in 0.09s
    ```
    test_two_tasks_under_one_condition_get_distinct_save_names (the new D20 test) PASSED.
    Two B-1 arms receive distinct save-names derived from their unique run_uid slugs.

  - M2 arms differ only by skill injection — inline python snippet confirmed:
    ```
    B-noskill count: 1
    B-skill count: 1
    B-noskill system msg == base _SYSTEM: True
    B-skill system contains skill text: True
    B-skill system != B-noskill system: True
    B-noskill prompt == B-skill prompt: True
    B-noskill verification == B-skill verification: True
    Noskill id: 'b-b1-noskill'
    Skill id: 'b-b1-skill'
    ```
    B-skill system prompt = _SYSTEM + "\n\n" + SKILL.md content; B-noskill = _SYSTEM only.
    Both carry identical user prompt and ReadbackSpec verification.

  - run-m1 B wiring + evaluator config — all 9 tests:
    ```
    tests/experiments/test_m1_run.py::test_run_m1_threads_dset_per_condition PASSED
    tests/experiments/test_m1_run.py::test_run_m1_f_branch_yields_outcomes PASSED
    tests/experiments/test_m1_run.py::test_run_m1_skips_absent_domains_without_crashing PASSED
    tests/experiments/test_m1_run.py::test_run_m1_b_branch_yields_outcomes PASSED
    tests/experiments/test_evaluator_config_b.py::test_loads_candidate_config PASSED
    tests/experiments/test_evaluator_config_b.py::test_loads_oracle_b_set_project_and_goldens PASSED
    tests/experiments/test_evaluator_config_b.py::test_missing_candidate_section_raises_clear_value_error PASSED
    tests/experiments/test_evaluator_config_b.py::test_missing_project_id_raises_clear_value_error PASSED
    tests/experiments/test_evaluator_config_b.py::test_missing_goldens_subtable_raises_clear_value_error PASSED
    9 passed in 0.11s
    ```

  - Full suite + lint:
    ```
    945 passed in 27.58s
    ```
    ```
    All checks passed!
    195 files already formatted
    ```
    Zero failures. Ruff check + format clean over whole repo (CI parity).

Oracle discrimination after F2 fix: golden PASS / missing-object FAIL / 4 mutants FAIL / reorder PASS / wrong-value FAIL
Note: live MSTR readback DEFERRED — deterministic stubbed path verified.
Failures: none
