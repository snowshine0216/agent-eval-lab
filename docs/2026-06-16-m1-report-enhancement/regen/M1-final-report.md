# M1 model characterization report — M1-agentic-v1

- spec_hash: `ca4467f2fbf15ddf59ebf976b3691ae937c7aed75b233ef50a0133683b12b41e` · dataset_snapshot_hash: `d75f48f3f1a97da6edbdc7eb5b059d9f4723acc406cde6b47e65f1e7cb0aa85c` · pricing_snapshot_hash: `94d8d83ffd1cbd8f97961a3cd07ea70ddd821a28162782dd4dc84988b55a5548` (snapshot 2026-06-13)
- k=5 valid trials · bootstrap seed=20260613 · n_resamples=2000 · alpha=0.05 · classifier fc-v4
- conditions present: deepseek:deepseek-v4-pro, glm:Pro/zai-org/GLM-5.1, minimax:MiniMax-M3, siliconflow:Qwen/Qwen3.5-397B-A17B, siliconflow:Qwen/Qwen3.6-35B-A3B
- domains not yet run: B (rendered as 'not yet run', not as failures)

## Per-domain scores (primary metric: pass^k)

| condition | domain | pass^k [95% CI] | CI method | valid | invalid |
| --- | --- | --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | F | 0.000 [0.000, 0.708] | binomial_exact | 15 | 0 |
| deepseek:deepseek-v4-pro | D | INCOMPLETE (VOID) | cluster_bootstrap | 0 | 0 |
| glm:Pro/zai-org/GLM-5.1 | F | 0.000 [0.000, 0.708] | binomial_exact | 15 | 0 |
| minimax:MiniMax-M3 | F | 0.000 [0.000, 0.708] | binomial_exact | 15 | 0 |
| minimax:MiniMax-M3 | D | INCOMPLETE (VOID) | cluster_bootstrap | 0 | 0 |
| siliconflow:Qwen/Qwen3.5-397B-A17B | F | 0.000 [0.000, 0.708] | binomial_exact | 15 | 0 |
| siliconflow:Qwen/Qwen3.6-35B-A3B | F | 0.333 [0.008, 0.906] | binomial_exact | 15 | 0 |
| (all conditions) | B | not yet run | — | 0 | 0 |

## Per-domain headlines

- **D** — best pass^k: `deepseek:deepseek-v4-pro` (0.000); cheapest on cost-frontier: `—`
- **F** — best pass^k: `siliconflow:Qwen/Qwen3.6-35B-A3B` (0.333); cheapest on cost-frontier: `siliconflow:Qwen/Qwen3.6-35B-A3B`

## Macro composite

Equal-weighted mean of per-domain primary estimates (weights: B=1.0, D=1.0, F=1.0); weighted by DOMAIN, never a raw task pool (D23). CI method: `weighted_halfwidth_propagation` (conservative half-width propagation under independence; the composite over K=3 domains has no defensible bootstrap CI).

| condition | composite | note |
| --- | --- | --- |
| deepseek:deepseek-v4-pro | 0.000 [0.000, 0.354] | reduced coverage (some domains not run / void) |
| glm:Pro/zai-org/GLM-5.1 | 0.000 [0.000, 0.354] | reduced coverage (some domains not run / void) |
| minimax:MiniMax-M3 | 0.000 [0.000, 0.354] | reduced coverage (some domains not run / void) |
| siliconflow:Qwen/Qwen3.5-397B-A17B | 0.000 [0.000, 0.354] | reduced coverage (some domains not run / void) |
| siliconflow:Qwen/Qwen3.6-35B-A3B | 0.333 [0.000, 0.782] | reduced coverage (some domains not run / void) |

> Composite computed over present domains only; not yet run: B.

## Efficiency & cost

Per (condition, domain). Rounds are time-to-completion (right-censored for budget-capped runs); tokens and cost are observed over ALL valid runs incl. capped (never censored).

| condition | domain | rounds median [min–max] | prompt tok | completion tok | total tok | cost (USD) | tool calls | safety-cap hits | max-rounds hits | dominant stop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | F | 9 [3–21] | 1086928 | 73185 | 1160113 | 2.1459 | 161 | 0 | 0 | completed_natural |
| deepseek:deepseek-v4-pro | D | 0 [0–0] | 0 | 0 | 0 | — | 0 | 0 | 0 | — |
| glm:Pro/zai-org/GLM-5.1 | F | 103.5 [5–200] (5 right-censored at cap) | 9327515 | 56393 | 9383908 | 9.3147 | 1031 | 5 | 0 | completed_natural |
| minimax:MiniMax-M3 | F | 16 [7–55] | 1733525 | 104966 | 1838491 | 1.2920 | 249 | 0 | 0 | completed_natural |
| minimax:MiniMax-M3 | D | 0 [0–0] | 0 | 0 | 0 | — | 0 | 0 | 0 | — |
| siliconflow:Qwen/Qwen3.5-397B-A17B | F | 4 [3–162] | 5095347 | 58248 | 5153595 | 2.9495 | 486 | 0 | 0 | completed_natural |
| siliconflow:Qwen/Qwen3.6-35B-A3B | F | 8 [3–27] | 812029 | 50575 | 862604 | 0.2433 | 131 | 0 | 0 | completed_natural |

## Pareto frontiers (success vs efficiency, per domain)

### D — pass^k vs cost_usd

| condition | pass^k | cost_usd | on frontier |
| --- | --- | --- | --- |

### D — pass^k vs rounds

| condition | pass^k | rounds | on frontier |
| --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | 0.000 | 0 | yes |
| minimax:MiniMax-M3 | 0.000 | 0 | yes |

### D — pass^k vs tokens

| condition | pass^k | tokens | on frontier |
| --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | 0.000 | 0 | yes |
| minimax:MiniMax-M3 | 0.000 | 0 | yes |

### F — pass^k vs cost_usd

| condition | pass^k | cost_usd | on frontier |
| --- | --- | --- | --- |
| siliconflow:Qwen/Qwen3.6-35B-A3B | 0.333 | 0.2433 | yes |
| minimax:MiniMax-M3 | 0.000 | 1.292 | — |
| deepseek:deepseek-v4-pro | 0.000 | 2.146 | — |
| siliconflow:Qwen/Qwen3.5-397B-A17B | 0.000 | 2.95 | — |
| glm:Pro/zai-org/GLM-5.1 | 0.000 | 9.315 | — |

### F — pass^k vs rounds

| condition | pass^k | rounds | on frontier |
| --- | --- | --- | --- |
| siliconflow:Qwen/Qwen3.5-397B-A17B | 0.000 | 4 | yes |
| glm:Pro/zai-org/GLM-5.1 | 0.000 | 6 | — |
| siliconflow:Qwen/Qwen3.6-35B-A3B | 0.333 | 8 | yes |
| deepseek:deepseek-v4-pro | 0.000 | 9 | — |
| minimax:MiniMax-M3 | 0.000 | 16 | — |

### F — pass^k vs tokens

| condition | pass^k | tokens | on frontier |
| --- | --- | --- | --- |
| siliconflow:Qwen/Qwen3.6-35B-A3B | 0.333 | 8.626e+05 | yes |
| deepseek:deepseek-v4-pro | 0.000 | 1.16e+06 | — |
| minimax:MiniMax-M3 | 0.000 | 1.838e+06 | — |
| siliconflow:Qwen/Qwen3.5-397B-A17B | 0.000 | 5.154e+06 | — |
| glm:Pro/zai-org/GLM-5.1 | 0.000 | 9.384e+06 | — |

## Planned comparisons (Holm-corrected, two-sided; effect = metric(b) − metric(a))

| comparison | domain | Δ pass^k [CI] | p | Holm-adj p | rejected |
| --- | --- | --- | --- | --- | --- |
| deepseek_vs_glm | D | (skipped — arm not run) | — | — | — |
| deepseek_vs_minimax | D | (skipped — arm not run) | — | — | — |
| deepseek_vs_local-Qwen3-8B | D | (skipped — arm not run) | — | — | — |
| deepseek_vs_qwen3.5-397b | D | (skipped — arm not run) | — | — | — |
| deepseek_vs_qwen3.6-35b | D | (skipped — arm not run) | — | — | — |
| glm_vs_minimax | D | (skipped — arm not run) | — | — | — |
| glm_vs_local-Qwen3-8B | D | (skipped — arm not run) | — | — | — |
| glm_vs_qwen3.5-397b | D | (skipped — arm not run) | — | — | — |
| glm_vs_qwen3.6-35b | D | (skipped — arm not run) | — | — | — |
| minimax_vs_local-Qwen3-8B | D | (skipped — arm not run) | — | — | — |
| minimax_vs_qwen3.5-397b | D | (skipped — arm not run) | — | — | — |
| minimax_vs_qwen3.6-35b | D | (skipped — arm not run) | — | — | — |
| local-Qwen3-8B_vs_qwen3.5-397b | D | (skipped — arm not run) | — | — | — |
| local-Qwen3-8B_vs_qwen3.6-35b | D | (skipped — arm not run) | — | — | — |
| qwen3.5-397b_vs_qwen3.6-35b | D | (skipped — arm not run) | — | — | — |

## Failure classification (fc-v4) per condition

### deepseek:deepseek-v4-pro

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | oracle_red | 13 |

### glm:Pro/zai-org/GLM-5.1

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | budget_exhausted | 5 |
| agent_failure | oracle_red | 5 |
| agent_failure | other_miss | 5 |

### minimax:MiniMax-M3

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | oracle_red | 15 |

### siliconflow:Qwen/Qwen3.5-397B-A17B

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | oracle_red | 12 |

### siliconflow:Qwen/Qwen3.6-35B-A3B

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | oracle_red | 10 |

## Validity mask / invalid-rate / void

Max invalid-rate (VOID threshold): 0.40; k=5 valid trials required per task (D34). A task that voids before k valid trials is INCOMPLETE and excluded from pass^k — never scored over <k.

| condition | domain | valid | invalid | invalid-rate | void tasks |
| --- | --- | --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | F | 15 | 0 | 0.000 | 0 |
| deepseek:deepseek-v4-pro | D | 0 | 0 | 0.000 | 15 |
| glm:Pro/zai-org/GLM-5.1 | F | 15 | 0 | 0.000 | 0 |
| minimax:MiniMax-M3 | F | 15 | 0 | 0.000 | 0 |
| minimax:MiniMax-M3 | D | 0 | 0 | 0.000 | 15 |
| siliconflow:Qwen/Qwen3.5-397B-A17B | F | 15 | 0 | 0.000 | 0 |
| siliconflow:Qwen/Qwen3.6-35B-A3B | F | 15 | 0 | 0.000 | 0 |

## Subreports

- [`M1-D-report.md`](M1-D-report.md)
- [`M1-F-report.md`](M1-F-report.md)
- [`M1-F-failure-analysis.md`](M1-F-failure-analysis.md) (hand-authored companion)
- [`M1-F-report-NOTES.md`](M1-F-report-NOTES.md) (hand-authored companion)

