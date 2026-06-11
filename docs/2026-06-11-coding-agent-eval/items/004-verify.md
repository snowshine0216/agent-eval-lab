Verdict: PASS

Subagent: sonnet
Source: smoke-test run on branch claude/coding-agent-eval-004 (2026-06-12)
Entry point exercised: `uv run python -m agent_eval_lab.cli report-final`

## Observed behavior per criterion group

### A. Code-world live-run wiring

- **A1 world resolver** — `src/agent_eval_lab/runners/worlds.py` is a pure `resolve_world(available_tools) -> WorldBinding` with a closed two-entry table; raises `ValueError` on empty list, unknown names, and cross-world mix. Tests: `test_pure_workspace_set_resolves_to_workspace_binding`, `test_pure_code_set_resolves_to_code_binding_with_pytest_executor`, `test_partial_code_set_still_resolves_to_code_binding`, `test_cross_world_mix_raises_value_error_naming_offenders`, `test_unknown_name_raises_value_error_naming_it`, `test_empty_tool_list_raises_value_error`, `test_registries_are_disjoint_load_bearing_invariant` (tests/runners/test_worlds.py).
- **A2 executor** — `runners/pytest_edge.execute_request` satisfies the `Executor` type; integration tests: `test_loop_fulfills_execution_request_as_tool_success`, `test_execute_request_fulfills_run_tests_through_the_loop` (tests/runners/test_loop_effects.py). NO_CHOICES_ERROR shared constant confirmed in `records/trajectory.py`; referenced by both `loop.py` and `classify.py`; pinned by `test_loop.py:317`.
- **A3 run_task_k threading** — `run_task_k` accepts `apply_fn`/`executor` with workspace defaults. Tests: `test_run_task_k_defaults_yield_byte_identical_workspace_run`, `test_run_task_k_threads_code_world_binding_to_run_single` (tests/runners/test_multi_run.py). Code-world task with stub HTTP client fulfills `run_tests`, records `ToolSuccess`, grades through oracle edge, `grade.passed=True`.
- **A4 CLI wiring** — `cli.run_baseline` resolves world per task via `worlds.resolve_world`; no hardwired `WORKSPACE_TOOLS`. Test: `test_run_baseline_resolves_code_world_and_grades_through_oracle` (tests/test_cli.py).
- **A5 fail-loud reachability** — connect error exits 1 with provider id + base_url + "is the server running?" hint. Test: `test_run_baseline_connect_error_exits_1_with_provider_and_hint` (tests/test_cli.py:935). `--max-tokens` flag exists in `run-baseline --help` (default=4096, help text confirmed).

### B. Failure classifier

- **B6 module and shape** — `src/agent_eval_lab/reports/classify.py` exposes `classify_run(run) -> RunClassification` (frozen dataclass). `classifier_version = "fc-v2"`. Hypothesis property test: `test_classify_run_is_total_and_closed` (tests/reports/test_classify_properties.py:124) — feeds arbitrary RunResult, asserts never raises, always returns closed category.
- **B7 mapping table** — All 16 rows unit-tested in tests/reports/test_classify.py (`test_row_01_passed` through `test_row_16_fallback_other_miss`; fc-v2 additions: `test_token_budget_exhausted_classification`, `test_parse_failure_none_record_classifies_as_harness_failure`). Row-8 closes error branch by construction (foreign_verdict fallback). Rows 7/8 ordered: tree_collision named first, fallback second.
- **B8 taxonomy untouched** — `FailureCategory` unchanged; `test_failure_category_member_set_is_unchanged` (tests/reports/test_classify.py:282). fc-v2 adds `token_budget_exhausted` to `Subcategory`, vocabulary now 16: `test_subcategory_vocabulary_is_closed_at_16_after_fc_v2` (tests/reports/test_classify.py:310).
- **B9 task-defect queue** — Implemented in `reports/final.py`; unit-tested: `test_task_defect_candidate_on_unanimous_failure`, `test_no_candidate_when_one_condition_passes`, `test_blocked_condition_excluded_from_unanimity`, `test_condition_without_records_for_task_is_vacuous` (tests/reports/test_final.py).
- **B10 pinned harness residuals** — Known-limitations section names dotted-path false-allow (criterion 10a) and rmtree/disk-full harness fault (criterion 10b); both confirmed in report lines 128-129.

### C. Live baseline runs

- **C11 run matrix** — 4×45=180 runs committed to `docs/2026-06-11-coding-agent-eval/runs/` (deepseek, glm, minimax, local). Verified with `wc -l`: 45 per file.
- **C12 artifact isolation** — Live run output goes to `reports/code-repair/`; Weeks 3-4 artifacts in `reports/` not overwritten (separate paths, gitignored).
- **C13 committed artifacts** — Four JSONLs committed under `docs/2026-06-11-coding-agent-eval/runs/`; every line round-trips through `_load_run_results` (the loader was used in the byte-det regen test).
- **C14 cost capture** — `docs/2026-06-11-coding-agent-eval/prices.json` present with `snapshot_date` + `prices` keyed by `condition_id`; local condition renders "not computed" in report (confirmed line 91).

### D. Final evaluation report (exit gate)

- **D15 command** — `report-final --help` exits 0, all flags documented (`--runs`, `--dataset`, `--tiers`, `--prices`, `--context-file`, `--k`, `--expected-n-tasks`, `--seed`, `--n-resamples`, `--alpha`, `--out`). Middle `condition_id` segment cross-checked against records: `test_report_final_rejects_heterogeneous_runs_file`, `test_report_final_rejects_condition_segment_mismatch` (tests/test_cli.py).
- **D16 report sections** — All 12 spec-ordered sections confirmed present: header, per-condition pass@1/pass^3 with 95% CIs, per-tier, per-capability, failure classification (fc-v2), task-defect candidates ("none"), cost and latency, context (v2 baseline), discriminativeness verdict, known limitations, roadmap takeaways, excluded conditions.
- **D17 discriminativeness verdict** — Mechanical rule reused from `reports/validation.py`; renders "none" (weak=False, strong=False) with n=15 honesty line. Regression test guards byte-identity of `report-validation` output after any shared extraction.
- **D18 known limitations** — 8 items confirmed in report; includes ADR-0010 trust boundary, no kernel sandbox, n=15 wide CIs, dotted-path false-allow, rmtree leak, hosted non-determinism, gpt-5.5 block, budget asymmetry (C1/C2 pre-fix trajectories).
- **D19 byte-deterministic regeneration** — Regenerated to `/tmp/final-report-regen.md` with the exact footer command; `diff` returned `BYTE_IDENTICAL`. Test: `test_report_final_renders_byte_identically_across_invocations` (tests/test_cli.py:1027); `test_build_and_render_are_byte_deterministic` (tests/reports/test_final.py:90). No generation timestamp anywhere: `test_no_generation_timestamp_anywhere` (tests/reports/test_final.py:103).
- **D20 exit-gate artifact** — `docs/2026-06-11-coding-agent-eval/final-evaluation-report.md` committed; generated from real run data; blocked condition handling tested: `test_blocked_condition_renders_blocked_without_fabricated_numbers` (tests/reports/test_final.py:111).

### E. Engineering gates

- **E21 TDD evidence** — Every mapping row has a dedicated unit test; property tests (Hypothesis) cover totality and determinism; integration tests drove stub-model paths before implementation (per git history and review ledger).
- **E22 CI and style** — `uv run pytest`: **664 passed** in 20.65s, 0 failed. `uv run ruff check .`: **clean**. `uv run ruff format --check .`: **clean**. No new CI lane; no live model calls in tests; functional core / imperative shell preserved (`classify.py` and `reports/final.py` are pure; I/O confined to `cli.py`).

## Classification verification

All 180 committed runs classified under fc-v2 with no errors: 45×4 = 180 total, all `passed` (the post-fix rerun saturates every condition). Zero unclassified.

## Failures

none
