# Configuration comparison — default vs planning

## Hypothesis (pre-declared, frozen before any run)

Configuration B (planning) achieves a higher pass^3 on the hard tiers (T3+T4) than Configuration A, because the v1/v2 failure signal is over-calling and mis-tracking derived/minted ids on multi-step chains; an explicit 'identify before you modify' step should suppress extra_call and wrong_args on multi_step_state / derived_reasoning / constraint_compliance tasks. On T1+T2 the two configs are expected to be statistically indistinguishable (both near-ceiling).

## Held-fixed factors

- Model: `deepseek:deepseek-v4-pro` · dataset: `workspace_tool_use_v2` (all 50 tasks, paired) · k=3
- Temperature 0.0 *requested* (no seed sent; hosted providers are not greedy-deterministic at temp 0).
- Registry: WORKSPACE_TOOLS · per-task max_steps honored (ADR-0004).

## Prompt-config pins (ADR-0007: configs share condition_id; identity is the source path)

- Config A — default (per-task author prompt, no override)
  - artifact: `reports/runs-deepseek-deepseek-v4-pro.jsonl`
- Config B — planning (planning-v1 fixture)
  - artifact: `reports/runs-deepseek-deepseek-v4-pro__planning-v1.jsonl`
  - planning prompt sha256 (over canonical bytes): `7bd62a40b2050e2b061a11d2cf63eb942b566556441eeec2dcb9b34c95051cff`

## Per-configuration pass rates

| metric | A (default) | B (planning) |
| --- | --- | --- |
| pass^3 (overall, 50 tasks) | 1.000 | 0.980 |
| pass@1 (trial) | 1.000 | 0.987 |

### Per-tier pass^3

| tier | A | B |
| --- | --- | --- |
| T1 | 1.000 | 1.000 |
| T2 | 1.000 | 0.917 |
| T3 | 1.000 | 1.000 |
| T4 | 1.000 | 1.000 |

## Paired Δ pass^3 (B − A), cluster-bootstrap-by-task 95% CI

- **Primary (T3+T4):** Δ = +0.000 [+0.000, +0.000] (seed=20260610, n_resamples=2000)
- Secondary (overall 50 tasks, descriptive): Δ = -0.020 [-0.060, +0.000]

## Secondary metrics (mechanism + cost; not decisive)

| metric | A | B |
| --- | --- | --- |
| extra_call rate | 0.000 | 0.013 |
| wrong_args rate | 0.000 | 0.000 |
| prompt tokens | 469509 | 501712 |
| completion tokens | 43369 | 57740 |

## Decision rule (frozen before running) and verdict

- If the T3+T4 Δ pass^3 95% CI excludes 0 and lies above 0 → planning helps on hard tiers.
- If the CI includes 0 → no detectable effect at n=50 (absence of a detectable effect is not evidence of no effect).
- If the CI excludes 0 and lies below 0 → planning hurts.

**Verdict (read mechanically off the T3+T4 Δ CI):** no detectable effect at n=50 — the T3+T4 Δ CI includes 0. With 50 tasks and near-ceiling rates the interval is wide; absence of a detectable effect is not evidence of no effect.
