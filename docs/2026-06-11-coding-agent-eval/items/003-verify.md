Verdict: PASS

Subagent: sonnet
Source: branch claude/coding-agent-eval-003 (HEAD at time of run)
Entry point exercised: `tasks/loader.load_tasks` → `runners/oracle_edge.precompute_execution_verdicts` → `graders/dispatch.grade_trajectory` + `tests/datasets/test_code_repair_v1.py` conformance suite

## Observed behavior per criterion

### Throwaway script `/tmp/verify_003.py` — all checks green

**Step A — dataset shape and loader (criteria 1–2)**

- `load_tasks("examples/datasets/code_repair_v1.jsonl")` → 15 tasks, ids `cr-001..cr-015`, regex `^cr-\d{3}$`, unique. PASS.
- Every row parses into a `Task` with exactly one reachable `ExecutionSpec`. PASS.
- Every row: `split="dev"`, `version="1"`, `provenance="hand_written"`, `review="passed:cr-rubric-v1"`, `world_template_id` matching `^code-v1-[a-z0-9-]+$`, unique per task, `max_steps` present. PASS.
- All 15 tasks have exactly 2 message turns; system turn is byte-identical across all rows. PASS.

**Step B — tiers sidecar (criterion 3)**

`code_repair_v1_tiers.json` → 15 entries, T1=2, T2=4, T3=6, T4=3, keys match dataset ids. PASS.

**Step C — review-fixtures sidecar (criteria 6, 9)**

`code_repair_v1_review_fixtures.json` → 15 entries; every entry has `{bug_class, solution, hack, distractor_paths}`; all bug classes in closed 6-value vocabulary; all 6 classes represented ≥ 1×. PASS.

**Step D — oracle pipeline on 3 tasks (criteria 11, 12, 14)**

Three tasks exercised across tiers — cr-001 (T1), cr-009 (T3), cr-013 (T4).
For each: reference tree (initial ⊕ solution) → `passed=True`; initial tree → `passed=False`; hack tree (all three carried a hack fixture) → `passed=False`. PASS.

**Step E — additional criteria spot checks**

- Criterion 4: all 6 capabilities present, each covers ≥ 2 tasks; all task capabilities in closed vocabulary. PASS.
- Criterion 5: every T3/T4 task has a valid `difficulty_knob` from the closed 6-value vocabulary. PASS.
- Criterion 7 (available_tools): all 15 tasks have exactly `{read_file, write_file, list_files, run_tests}`. PASS.
- Criterion 8 (timeout_s): `None` on every `ExecutionSpec`. PASS.
- Criterion 16: ≥ 3 tasks use `AllOf` composition. PASS.
- Criterion 18: `max_steps` ≥ 6 all, ≥ 8 for T3/T4, ≤ 16. PASS.

**Step F — determinism (criterion 23)**

cr-001 reference tree graded twice end-to-end → byte-identical serialized `GradeResult` both runs. PASS.

### Conformance suite `tests/datasets/test_code_repair_v1.py` — 32 passed in 6.97s

| Criterion | Conformance test(s) |
|-----------|---------------------|
| 1 – dataset file and shape | `test_dataset_has_fifteen_uniquely_numbered_rows`, `test_every_row_has_a_reachable_execution_spec`, `test_messages_are_one_shared_system_turn_plus_one_user_turn` |
| 2 – metadata contract | `test_metadata_contract_on_every_row`, `test_available_tools_are_exactly_the_code_world_tools` |
| 3 – tier sidecar | `test_tier_sidecar_covers_every_id_with_declared_allocation` |
| 4 – capability taxonomy | `test_capabilities_closed_and_each_covers_at_least_two_tasks` |
| 5 – difficulty knobs | `test_every_hard_task_declares_exactly_one_vocabulary_knob` |
| 6 + 9 – bug classes + fixtures sidecar | `test_fixtures_sidecar_shape_and_bug_class_coverage`, `test_solution_and_hack_paths_stay_inside_the_initial_tree` |
| 7 – world validity | `test_every_fixture_tree_is_a_valid_code_world_tree` |
| 8 – oracle invariants | `test_oracle_paths_are_disjoint_from_the_initial_tree`, `test_oracle_is_collectible_with_unique_test_module_basenames` |
| 10 – symptom is real | `test_initial_tree_fails_visible_suite_or_is_prose_only`, `test_prose_only_tasks_are_exactly_the_prose_localization_tasks` |
| 11 – solvability | `test_reference_solution_passes_oracle_through_production_edge`, `test_reference_tree_passes_its_visible_suite` |
| 12 – no-op agent grades 0/15 | `test_noop_agent_fails_every_task` |
| 13 – test-stubbing neutralized | `test_stubbing_visible_tests_cannot_pass_an_unrepaired_task` |
| 14 – hardcode agent caught | `test_hack_fixtures_cover_overfit_and_t4_tasks`, `test_hacked_tree_passes_visible_suite_but_fails_oracle` |
| 15 – anti-rote transcription proxy | `test_prompt_never_dictates_a_solution_line` |
| 16 – policy composition | `test_at_least_three_tasks_compose_execution_with_policy`, `test_max_tool_calls_budgets_fit_inside_max_steps`, `test_no_tool_call_legs_name_a_registered_tool`, `test_only_modifies_allowlists_pass_the_dotted_path_ambiguity_guard` |
| 17 – distractor files | `test_distractor_files_are_real_untouched_and_oracle_referenced` |
| 18 – max_steps floors | `test_max_steps_floors_and_cap` |
| 19 – hermeticity banlist | `test_no_fixture_file_imports_a_banned_module` |
| 20 – oracle leakage | `test_prompt_never_leaks_an_oracle_line` |
| 21 – authoring rubric + review ledger | `test_review_ledger_has_exactly_one_block_of_ids_matching_dataset` |
| 22 – conformance suite in CI | Suite runs under default `pytest` gate; 32 tests in 6.97s (well within 120s budget) |
| 23 – determinism | `test_grading_the_same_reference_tree_twice_is_byte_identical` |
| 24 – TDD evidence | No `src/agent_eval_lab` production changes on this branch; all conformance tests pass against the dataset |

### Full suite

582 tests passed in 16.65s. No regressions.

## Failures: none
