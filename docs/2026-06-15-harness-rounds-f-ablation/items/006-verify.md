Verdict: PASS

## Subagent

Claude Code (claude-sonnet-4-6), 2026-06-15.

## Source / Entry Points

- `src/agent_eval_lab/experiments/ablation_order.py` — pure `ablation_run_order` + `RunUnit`
- `src/agent_eval_lab/experiments/f_ablation_spec.py` — `AblationPolicy`, `ablation_policy`, `freeze_ablation_policy`, `build_f_ablation_spec`, `ABLATION_SEED`
- `src/agent_eval_lab/cli.py` — `run-f-ablation` subcommand / `_run_f_ablation_command`
- Tests: `tests/experiments/test_ablation_order.py`, `tests/experiments/test_f_ablation_spec.py`, `tests/cli/test_run_f_ablation.py`

## Observed Behavior Per Criterion

### Pure `ablation_run_order`

**AC: deterministic, seeded, no I/O, covers all (model × task-arm × rep) exactly once.**

Direct import smoke (step 3):
```
count: 240 (expect 240)
unique units: 240 (expect 240)
seed42 reproducible: True
seed99 differs: True
```
Interleaving verified: block 0 arms `['feedback', 'prompt', 'both', 'bare']` (shuffled, not
canonical). Each of 5 blocks holds all 4 arms. Unit tests all PASS:
- `test_total_coverage_each_unit_exactly_once_at_k5` PASS
- `test_task_id_encodes_the_arm` PASS
- `test_same_seed_is_identical` PASS
- `test_different_seed_differs` PASS
- `test_no_wall_clock_dependence_two_calls_equal` PASS
- `test_arms_interleaved_within_each_block_not_arm_grouped` PASS

### `run-f-ablation` CLI driver

**AC: subcommand exists; one artifact per condition (12 task-arms inside); realized-order sidecar; no paid execution.**

`--help` output confirms subcommand with `--dry-run` flag:
```
usage: agent-eval-lab run-f-ablation [-h] --evaluator-config TOML [--out OUT]
    [--temperature TEMPERATURE] [--max-tokens MAX_TOKENS] [--dry-run]
  --dry-run   write the realized run order and exit WITHOUT any provider call
```

Tests (all PASS):
- `test_dry_run_writes_order_and_makes_zero_run_fn_calls` — dry-run writes 1 sidecar with
  240 entries, zero run_fn calls, no JSONL artifacts. Confirms no-network-call path.
- `test_real_path_with_fake_run_fn_writes_one_artifact_per_condition` — 4 artifacts
  (`runs-ablation-*-F.jsonl`), each contains all 12 task-arm ids and 60 rows (12×5). 1 sidecar,
  240 realized units.
- `test_realized_order_matches_the_frozen_pure_order` — sidecar order matches `ablation_run_order`
  with frozen seed `ABLATION_SEED=20260615`.
- `test_parser_exposes_run_f_ablation_with_dry_run` — parser roundtrip, `max_tokens=16384`.
- `test_dispatch_routes_run_f_ablation` — dispatch routes correctly.
- `test_transport_error_mid_run_aborts_cleanly_and_preserves_partial_results` — mid-run abort
  (after 5th call): rc != 0, sidecar present with exactly 5 entries, 5 JSONL rows on disk
  (streaming, not buffered).
- `test_task_id_skew_is_caught_before_any_run_fn_call` — task_id skew returns rc=1 with zero
  run_fn calls (validation before any paid call).

### Frozen `f_ablation_spec`

**AC: separate from m1_spec; 40-round policy; 12 task-arms; 4-model roster; seed frozen; m1 unaffected.**

Direct import verification:
```
max_rounds: 40 (expect 40)
seed: 20260615
k: 5
arms: ('bare', 'prompt', 'feedback', 'both')
task_arm_ids count: 12 (expect 12)
conditions: 4
experiment_id: F-ablation-v1
spec_hash before freeze: ''
spec_hash after freeze: fd8712f43489b25c...  (idempotent ✓)
policy_hash: f6977c920adf1342...  (idempotent ✓)
```

Unit tests:
- `test_roster_is_the_four_design_models` PASS
- `test_policy_records_40_rounds_12_arms_and_seed` PASS
- `test_policy_task_arm_ids_match_dataset_builder` PASS
- `test_spec_freezes_and_verifies_independently_of_m1` PASS
- `test_freeze_ablation_policy_is_deterministic_and_hashes_the_seed` PASS
- `test_building_the_ablation_spec_does_not_touch_m1` PASS

### Report compatibility

**AC: `_load_run_results` groups by `task_id`; no report-side change needed.**

`_load_run_results` loads `row["task_id"]` directly into `RunResult.task_id`. `pass_pow_k` is
keyed on `task_id`. Verified: 12 task-arms (4 arms × 3 bases), 9 all-pass → `pass_pow_k = 0.75`.
Test: `test_per_arm_pass_pow_k_separates_by_task_id_no_report_change` PASS.

### M1 frozen spec integrity

```
tests/experiments/test_m1_spec.py::... 24 passed
tests/experiments/test_spec_hash.py::... (included in above)
```
All 24 M1 tests still pass. No `ConditionDef`/`ExperimentSpec` schema change.

### No paid execution

Evidence: all 20 tests use injected fake `run_fn` (no network). The dry-run test asserts `calls
== []` with zero run_fn calls. No `ANTHROPIC_API_KEY` / provider credential accessed. CI guard
confirmed by test design (fake `run_fn_factory` / monkeypatched `_ablation_arm_tasks`).

### Linting / formatting

`ruff check` and `ruff format --check` pass on all 5 006 files: "All checks passed! / 5 files
already formatted."

## Test Summary

| Suite | Passed | Failed | Skipped |
|---|---|---|---|
| test_ablation_order.py | 6 | 0 | 0 |
| test_f_ablation_spec.py | 6 | 0 | 0 |
| test_run_f_ablation.py | 8 | 0 | 0 |
| **Total** | **20** | **0** | **0** |
| test_m1_spec.py + test_spec_hash.py | 24 | 0 | 0 |

## Failures

None.
