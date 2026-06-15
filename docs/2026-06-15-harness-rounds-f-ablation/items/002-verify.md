Verdict: PASS

## Subagent
claude-sonnet-4-6

## Source
Branch: `claude/harness-rounds-f-ablation-002`
Spec: `docs/2026-06-15-harness-rounds-f-ablation/items/002-spec.md`
Full suite: 1021 passed, 17 skipped, 0 failed.

## Entry points exercised

1. `uv run pytest -q -o addopts="" tests/runners/test_loop.py -k "max_rounds or round or cap or env_unhealthy"` — 9 passed
2. `uv run pytest -q -o addopts="" tests/records/test_serialize.py -k "round_trip or max_rounds or cf1"` — 11 passed
3. `uv run pytest -q -o addopts="" tests/runners/test_round_budget.py` — 5 passed
4. `uv run pytest -q -o addopts="" tests/runners/test_dset_run.py` — 7 passed (incl. F1 fix)
5. `uv run pytest -q -o addopts="" tests/experiments/test_aggregate.py tests/experiments/test_aggregate_efficiency.py` — 10 passed
6. `uv run pytest -q -o addopts="" -k "spec_hash"` — 21 passed
7. Full suite: `uv run pytest -q -o addopts=""` — 1021 passed, 17 skipped

## Observed behavior (one bullet per acceptance criterion)

- **Loop turn-bound fires at end-of-iteration (§A.1/A.2/A.3):** `src/agent_eval_lab/runners/loop.py:184-186` — after each round's tool calls apply, `if max_rounds is not None and rounds >= max_rounds: stop_reason = "max_rounds"; max_rounds_bound = True; break`. Tests `test_loop_stops_at_max_rounds_keeping_the_turns_work` and `test_loop_natural_completion_breaks_before_max_rounds` both PASS, confirming work is kept and natural completion breaks earlier. PASS.

- **`"max_rounds"` literal in `Trajectory.stop_reason`:** `src/agent_eval_lab/records/trajectory.py:59` lists `"max_rounds"` in the `Literal`. `_CAP_STOP_REASONS` already referenced it (N3 resolved). PASS.

- **`max_rounds_bound=True` on env_unhealthy post-probe:** `test_post_probe_unhealthy_with_max_rounds_sets_env_unhealthy_stop_reason` PASS — round-capped run with unhealthy post-probe records `stop_reason=env_unhealthy` with `max_rounds_bound=True` (F2 fix). PASS.

- **Trajectory gains three fields (§9.2):** `src/agent_eval_lab/records/trajectory.py:79-83` — `max_rounds: int | None = None`, `safety_cap: int | None = None`, `max_rounds_bound: bool = False`. PASS.

- **CF1 round-trip test (P1 mandatory):** `test_max_rounds_bound_survives_round_trip_cf1` (`tests/records/test_serialize.py:334`) — constructs `Trajectory(max_rounds=20, safety_cap=200, max_rounds_bound=True)`, serializes and deserializes, asserts all three survive. PASS.

- **Old records default safely (backward compat):** `test_old_v2_record_without_round_policy_keys_defaults_safely` (`tests/records/test_serialize.py:358`) — old dict without three keys deserializes with `max_rounds=None`, `safety_cap=None`, `max_rounds_bound=False`. PASS.

- **CF2 — direct attribute access replaces `getattr`:** `src/agent_eval_lab/metrics/reliability.py:32` uses `traj.safety_cap_bound or traj.max_rounds_bound` (direct); `src/agent_eval_lab/reports/classify.py:135` uses `traj.max_rounds_bound` (direct). No `getattr(traj, "max_rounds_bound", False)` in either file. PASS.

- **Per-domain defaults F=20/D=50 (§A.2/§11.3/ADR-0017):** `src/agent_eval_lab/runners/round_budget.py:17` — `DOMAIN_MAX_ROUNDS: dict[str, int] = {"F": 20, "D": 50}`. Test `test_default_per_domain_caps` PASS. PASS.

- **Task override > domain default:** `test_task_override_wins_over_domain_default` PASS. `test_unknown_domain_falls_back_to_task_override_or_none` PASS. PASS.

- **Non-positive `max_rounds` raises (F4 fix):** `test_resolve_max_rounds_rejects_zero_and_negative` PASS. PASS.

- **F1 fix — dset_run threads configured `safety_cap` (e.g. 300) not default 200:** `test_run_dset_threads_configured_safety_cap_not_default` (`tests/runners/test_dset_run.py:256`) — asserts `safety_cap=300` is forwarded, not the default 200. PASS.

- **dset_run threads resolved `max_rounds`:** `test_run_dset_threads_resolved_max_rounds` PASS. PASS.

- **Aggregation §D.3 — `n_censored` counts both `safety_cap_bound OR max_rounds_bound`:** `src/agent_eval_lab/experiments/aggregate.py:133-136` — `n_censored=sum(... if r.trajectory.safety_cap_bound or r.trajectory.max_rounds_bound)`. Test `test_efficiency_summary_counts_max_rounds_as_censored` PASS. PASS.

- **Aggregation §D.3 — resource sums include capped runs:** `test_efficiency_summary_tokens_include_capped_runs` PASS. PASS.

- **Aggregation §D.3 — time metrics censored:** `test_efficiency_summary_counts_safety_cap_as_censored` PASS (censoring applies for both cap types). PASS.

- **Frozen spec hash unbroken:** `uv run pytest -q -o addopts="" -k "spec_hash"` — 21 passed. Adding fields to `Trajectory`/serialize (record-level, not `ConditionDef`/`ExperimentSpec` schema) does not move frozen hashes. PASS.

- **Full suite green:** 1021 passed, 17 skipped, 0 failed. PASS.

## Failures

None.
