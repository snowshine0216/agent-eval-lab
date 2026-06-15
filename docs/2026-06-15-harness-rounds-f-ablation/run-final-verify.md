Verdict: PASS

Subagent: claude-sonnet-4-6
Source: /verify
Entry point exercised: `python -m agent_eval_lab.cli run-f-ablation --dry-run` + cross-item build smoke
Branch confirmed: autodev/harness-rounds-f-ablation-feature (16 commits ahead of main, 111 files changed)

## Cross-item flow observed

```
task-arms:             12   (build_f_task_arms — 003 arm-as-task, 3 bases × 4 arms)
order units:          240   (ablation_run_order — 006 driver, 4 models × 3 bases × 4 arms × k=5)
arm0 tree files:        6   (build_candidate_tree — 004 enriched trees)
ablation spec conds:    4   (build_f_ablation_spec — bare / prompt / feedback / both)
```

CLI `--dry-run` exit 0; sidecar `f-ablation.realized-order.json` written with 240 units, first entry `{model: deepseek:deepseek-v4-pro, task_id: f-f1-bare, repetition: 0}`. Zero run_fn calls (confirmed by unit test `test_dry_run_writes_order_and_makes_zero_run_fn_calls`: `assert calls == []`). No provider call made.

V-sandbox routing present (005): `build_candidate_tree` returns enriched tree; Factor V conditions wired through CLI → condition-level run artifacts.

## Full-suite counts

```
1095 passed, 18 skipped in 41.34s
```

User WIP (`tests/reports/test_validation.py`) — 18 passed (self-consistent, not a failure).

## M1 intact

```
tests/experiments/test_m1_spec.py + tests/experiments/test_spec_hash.py: 24 passed
```

001/002 changes to scoring did not move M1 frozen spec hash.

## Failures

None. The smoke script in the task used `build_f_ablation_spec()` with no args — the actual signature requires `dataset_snapshot_hash` and `pricing_snapshot_hash` keyword args. This is a task-script typo, not a code defect; all committed tests pass and the function is exercised correctly in `tests/experiments/test_f_ablation_spec.py`.
