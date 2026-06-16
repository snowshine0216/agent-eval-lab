# M1 subreport — D

- conditions: deepseek:deepseek-v4-pro, minimax:MiniMax-M3
- k=5 · tasks=15 · spec_hash=`ca4467f2fbf15ddf59ebf976b3691ae937c7aed75b233ef50a0133683b12b41e`

## Task quick-reference

| task | target_paths | grader | oracle tests |
| --- | --- | --- | --- |
| cmc-q01 | — | fact_key | — |
| cmc-q02 | — | fact_key | — |
| cmc-q03 | — | fact_key | — |
| cmc-q04 | — | fact_key | — |
| cmc-q05 | — | fact_key | — |
| cmc-q06 | — | fact_key | — |
| cmc-q07 | — | fact_key | — |
| cmc-q08 | — | fact_key | — |
| cmc-q09 | — | fact_key | — |
| cmc-q10 | — | all_of | — |
| cmc-q11 | — | all_of | — |
| cmc-q12 | — | all_of | — |
| cmc-q13 | — | all_of | — |
| cmc-q14 | — | all_of | — |
| cmc-q15 | — | all_of | — |

## Cross-model summary

| task | deepseek:deepseek-v4-pro | minimax:MiniMax-M3 | dominant stop |
| --- | --- | --- | --- |
| cmc-q01 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q02 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q03 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q04 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q05 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q06 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q07 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q08 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q09 | 2/2 ✅✅ | 2/2 ✅✅ | completed_natural |
| cmc-q10 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |
| cmc-q11 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |
| cmc-q12 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |
| cmc-q13 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |
| cmc-q14 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |
| cmc-q15 | 0/2 ❌❌ | 0/2 ❌❌ | completed_natural |

## Per-task detail

### Task: `cmc-q01`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=8685 / completion=708 / total=9393
- cost_usd: 0.017576
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=9044 / completion=579 / total=9623
- cost_usd: 0.006816
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q02`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 11 [4–18]
- tokens: prompt=112222 / completion=2992 / total=115214
- cost_usd: 0.205678
- tool calls (total): 20
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 16.5 [5–28]
- tokens: prompt=209183 / completion=2729 / total=211912
- cost_usd: 0.132059
- tool calls (total): 31
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q03`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=8745 / completion=795 / total=9540
- cost_usd: 0.017983
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 4 [3–5]
- tokens: prompt=11596 / completion=1192 / total=12788
- cost_usd: 0.009818
- tool calls (total): 6
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q04`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=8799 / completion=857 / total=9656
- cost_usd: 0.018293
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=9094 / completion=768 / total=9862
- cost_usd: 0.007300
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q05`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=8800 / completion=906 / total=9706
- cost_usd: 0.018465
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 4.5 [3–6]
- tokens: prompt=13579 / completion=976 / total=14555
- cost_usd: 0.010490
- tool calls (total): 7
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q06`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 26 [23–29]
- tokens: prompt=523284 / completion=10801 / total=534085
- cost_usd: 0.948102
- tool calls (total): 50
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 4 [3–5]
- tokens: prompt=11609 / completion=2643 / total=14252
- cost_usd: 0.013309
- tool calls (total): 6
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q07`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=8949 / completion=3340 / total=12289
- cost_usd: 0.027194
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 6 [3–9]
- tokens: prompt=18564 / completion=2133 / total=20697
- cost_usd: 0.016258
- tool calls (total): 10
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q08`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 3 [3–3]
- tokens: prompt=9018 / completion=3309 / total=12327
- cost_usd: 0.027207
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 6.5 [6–7]
- tokens: prompt=18288 / completion=2711 / total=20999
- cost_usd: 0.017479
- tool calls (total): 11
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q09`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 19 [9–29]
- tokens: prompt=379264 / completion=7982 / total=387246
- cost_usd: 0.687697
- tool calls (total): 36
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 2/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ✅✅
- rounds: 31.5 [11–52]
- tokens: prompt=666782 / completion=8158 / total=674940
- cost_usd: 0.419648
- tool calls (total): 61
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q10`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 35 [27–43]
- tokens: prompt=961729 / completion=11660 / total=973389
- cost_usd: 1.713985
- tool calls (total): 68
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 17 [9–25]
- tokens: prompt=119218 / completion=4800 / total=124018
- cost_usd: 0.083051
- tool calls (total): 32
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q11`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 22 [11–33]
- tokens: prompt=399881 / completion=8484 / total=408365
- cost_usd: 0.725317
- tool calls (total): 42
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 12 [8–16]
- tokens: prompt=99888 / completion=4321 / total=104209
- cost_usd: 0.070303
- tool calls (total): 22
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q12`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 75.5 [50–101]
- tokens: prompt=2441031 / completion=20709 / total=2461740
- cost_usd: 4.319461
- tool calls (total): 149
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 24 [12–36]
- tokens: prompt=405887 / completion=7226 / total=413113
- cost_usd: 0.260875
- tool calls (total): 46
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q13`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 5 [3–7]
- tokens: prompt=23659 / completion=5105 / total=28764
- cost_usd: 0.058932
- tool calls (total): 8
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 7 [4–10]
- tokens: prompt=24307 / completion=4433 / total=28740
- cost_usd: 0.025223
- tool calls (total): 12
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q14`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 6 [5–7]
- tokens: prompt=41918 / completion=5229 / total=47147
- cost_usd: 0.091134
- tool calls (total): 10
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 4 [3–5]
- tokens: prompt=16582 / completion=4868 / total=21450
- cost_usd: 0.021632
- tool calls (total): 6
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

### Task: `cmc-q15`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 30 [3–57]
- tokens: prompt=715733 / completion=9546 / total=725279
- cost_usd: 1.278595
- tool calls (total): 58
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/2 — **status = incomplete (excluded from pass^k)** (2/5 valid trials) — ❌❌
- rounds: 3 [3–3]
- tokens: prompt=9639 / completion=2723 / total=12362
- cost_usd: 0.012319
- tool calls (total): 4
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: failed
- edited: —
- out-of-scope edits: —

## Task-defect candidates

Tasks that every non-blocked condition with records unanimously fails. Flagged for human review, never auto-classified (ADR-0013).

- `cmc-q10` (2 conditions, 4 runs)
  - divergent failures (no shared unit)
- `cmc-q11` (2 conditions, 4 runs)
  - divergent failures (no shared unit)
- `cmc-q12` (2 conditions, 4 runs)
  - divergent failures (no shared unit)
- `cmc-q13` (2 conditions, 4 runs)
  - divergent failures (no shared unit)
- `cmc-q14` (2 conditions, 4 runs)
  - divergent failures (no shared unit)
- `cmc-q15` (2 conditions, 4 runs)
  - divergent failures (no shared unit)

## Per-condition efficiency

| condition | rounds median [min–max] | prompt tok | completion tok | total tok | cost (USD) | tool calls | safety-cap hits | max-rounds hits | dominant stop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | 4.5 [3–101] | 5651717 | 92423 | 5744140 | 10.1556 | 465 | 0 | 0 | completed_natural |
| minimax:MiniMax-M3 | 5 [3–52] | 1643260 | 50260 | 1693520 | 1.1066 | 262 | 0 | 0 | completed_natural |

## Failure classification (fc-v4) per task × condition

### `cmc-q10` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q10` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q11` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q11` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q12` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q12` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q13` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q13` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q14` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q14` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q15` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

### `cmc-q15` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | other_miss |
| agent_failure | other_miss |

