# F-ablation configurable roster — design

**Date:** 2026-06-16
**Status:** approved → implemented
**Related:** ADR-0019, `experiments/f_ablation_spec.py`, item 006 (harness-rounds-F-ablation)

## Problem

Rebuild the F-set ablation to compare **only** deepseek, minimax-m3, and
Qwen/Qwen3.6-35B-A3B (drop GLM). The roster was hard-coded in
`f_ablation_spec._CONDITIONS`, so changing which models compete meant a source
edit + test churn + re-freeze. Requirement from the user: make the roster
**configurable** so a future add/remove is a minimal change.

## Decision summary

The roster moves out of code into a committed TOML file; the spec builder becomes
pure over an explicit roster; `experiment_id` is bumped per roster change
(`F-ablation-v1` → `F-ablation-v2`). See ADR-0019 for the full rationale and the
options weighed (CLI flag, code constant).

## Components

1. **`f-ablation-roster.toml`** (repo root, committed). `experiment_id` + ordered
   `[[model]]` array of `{condition_id = "provider:model", label}`. Order is
   significant (feeds the seeded `ablation_run_order`).

2. **`experiments/f_ablation_roster.py`** (I/O at the edge). Frozen
   `FAblationRoster(experiment_id, conditions)` + `load_f_ablation_roster(path, *,
   valid_providers=None)`. Validates: present `experiment_id`; ≥1 model; each entry
   has `condition_id` + `label`; `condition_id` is `provider:model`; provider is in
   `valid_providers` when given. `valid_providers` is an explicit param (visible
   dependency) — the CLI passes `frozenset(PROVIDERS)` so typos die before any paid
   call; unit tests stay decoupled from the registry.

3. **`f_ablation_spec.build_f_ablation_spec`** — now pure over `conditions` +
   `experiment_id`; `_CONDITIONS` deleted. Frozen methodology (k=5, seed,
   40-round cap, `ARMS`, descriptive metric set) stays in code.

4. **CLI `run-f-ablation`** — gains `--roster PATH` (default the committed file),
   loads + freezes the spec, derives `models` from `spec.conditions`. Everything
   downstream already generalises to N models.

5. **Audit** — the realized-order sidecar records the resolved `experiment_id` +
   `spec_hash` alongside seed + order, so a run is reconstructable from artifacts
   now that the roster is config rather than frozen source.

## Data flow

`f-ablation-roster.toml` → `load_f_ablation_roster` → `FAblationRoster` →
`build_f_ablation_spec` → `freeze_spec` → `ablation_run_order(seed, models, …)` →
per-condition `runs-ablation-{slug}-F.jsonl` + `f-ablation.realized-order.json`.

## What stays the same

`m1_spec` untouched; `AblationPolicy`/`ARMS`/seed/k frozen; grading + run loop +
V-arm sandbox unchanged. Per-model: 3 bases × 4 arms × k=5 = 60; 3 models = **180**.

## Testing

- `test_f_ablation_roster.py`: committed default = 3-model v2; order preserved;
  missing experiment_id / empty roster / bad `condition_id` / unknown provider /
  missing label all raise clear `ValueError`s.
- `test_f_ablation_spec.py`: builder carries given conditions + id; freezes &
  verifies independently of m1.
- `test_run_f_ablation.py`: dry-run = 180 units + sidecar id/hash; real (fake
  run_fn) = 180 calls + 3 artifacts; realized order matches the pure 3-model order;
  `--roster` default + override parsed.
