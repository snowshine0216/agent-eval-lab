# F-ablation roster is config-driven (TOML) and versioned per change

The F-set ablation's competing models were frozen in code: `_CONDITIONS` in
`experiments/f_ablation_spec.py` hard-coded the 4-model roster (deepseek, GLM,
minimax, Qwen), and `build_f_ablation_spec` read that constant. Changing which
models compete — the most common operational edit to this experiment — therefore
required a source edit, new tests, and a re-freeze, even though the *methodology*
(k, seed, the uniform 40-round cap, the 2×2 arms, the descriptive metrics) was
unchanged. The roster is data, not logic; binding it in code coupled "what we
compare" to "how we compare."

The trigger: restrict the ablation to deepseek, minimax, and Qwen3.6-35B-A3B
(drop GLM — also the rung observed to abort mid-run on a SiliconFlow HTTP 400,
`runners/history.py`). Rather than swap one hard-coded list for another, the
roster becomes an explicit, version-controlled input.

## Considered Options

- **Roster in a committed TOML file, parsed at the edge** (chosen).
  `f-ablation-roster.toml` (repo root, parity with `evaluator.toml`, but
  committed — model names are not secret) lists `experiment_id` plus an ordered
  `[[model]]` array (`condition_id` = `provider:model`, `label`).
  `experiments/f_ablation_roster.py::load_f_ablation_roster` reads it with
  `tomllib`, validates each `condition_id` parses and (given the registry) names
  a registered provider, and returns a frozen `FAblationRoster`.
  `build_f_ablation_spec` stays pure — it takes `conditions` + `experiment_id`
  explicitly. Add/remove a model = a TOML edit, no code change; provider typos are
  caught at load, before any paid call. The CLI gains `--roster` (default the
  committed file).
- **CLI `--models` flag with a code-constant default.** Rejected: a roster passed
  ad-hoc per invocation is not version-controlled, so the actual comparison is
  reconstructable only from shell history, and labels (e.g. the Qwen PROVISIONAL
  note) have nowhere to live.
- **Keep a single code constant, parameterise the builder.** Rejected: still a
  code edit (+ test churn + re-freeze) for every roster change — the exact cost we
  set out to remove.

## Decision

The roster lives in `f-ablation-roster.toml`. `build_f_ablation_spec` is pure over
`(conditions, experiment_id, …)`. `experiment_id` is **bumped in the TOML whenever
the roster changes** (here `F-ablation-v1` → `F-ablation-v2`) so each distinct
comparison has a distinct frozen identity. Because the roster is no longer
reconstructable from frozen source, each run's realized-order sidecar
(`f-ablation.realized-order.json`) now records the resolved `experiment_id` and
`spec_hash` alongside the seed and order — the run is auditable from its artifacts.

The frozen methodology stays in code (`f_ablation_spec.py`): k=5, the seed, the
uniform 40-round cap, the 2×2 `ARMS`, the descriptive single-family metric set.
`m1_spec` is untouched.

## Consequences

- Reshaping the comparison (add/remove/reorder a model, bump the id) is a
  single-file config edit. Entry order is significant — it feeds the seeded
  `ablation_run_order`, so the realized order stays reproducible from the file.
- A genuinely new *provider* still needs one `runners/config.py::PROVIDERS` entry
  (base_url + api_key_env) — irreducible, and validated at roster load.
- Auditability shifts from "read the frozen constant" to "read the sidecar's
  `experiment_id` + `spec_hash`". The v1 (4-model) spec is no longer emitted by
  code; its identity survives in git history and prior phase records.
- `F-ablation-v2` roster = deepseek-v4-pro, MiniMax-M3, Qwen/Qwen3.6-35B-A3B →
  3 models × 3 bases × 4 arms × k=5 = **180 attempts** (was 240).
