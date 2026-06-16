# M1 subreport — F

- conditions: deepseek:deepseek-v4-pro, glm:Pro/zai-org/GLM-5.1, minimax:MiniMax-M3, siliconflow:Qwen/Qwen3.5-397B-A17B, siliconflow:Qwen/Qwen3.6-35B-A3B
- k=5 · tasks=3 · spec_hash=`ca4467f2fbf15ddf59ebf976b3691ae937c7aed75b233ef50a0133683b12b41e`

## Task quick-reference

| task | target_paths | grader | oracle tests |
| --- | --- | --- | --- |
| f-f1 | `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`, `tests/wdio/pageObjects/common/LibraryNotification.js` | node_execution | 5 |
| f-f2 | `tests/wdio/wdio.conf.ts` | node_execution | 4 |
| f-f3 | `tests/wdio/utils/failure-analysis/report-to-allure.js` | node_execution | 35 |

## Cross-model summary

| task | deepseek:deepseek-v4-pro | glm:Pro/zai-org/GLM-5.1 | minimax:MiniMax-M3 | siliconflow:Qwen/Qwen3.5-397B-A17B | siliconflow:Qwen/Qwen3.6-35B-A3B | dominant stop |
| --- | --- | --- | --- | --- | --- | --- |
| f-f1 | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | completed_natural |
| f-f2 | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | 0/5 ❌❌❌❌❌ | completed_natural |
| f-f3 | 2/5 ✅❌❌❌✅ | — admin (not executed) | 0/5 ❌❌❌❌❌ | 3/5 ❌✅✅❌✅ | 5/5 ✅✅✅✅✅ | completed_natural |

## Per-task detail

### Task: `f-f1`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 9 [6–13]
- tokens: prompt=330723 / completion=22394 / total=353117
- cost_usd: 0.653389
- tool calls (total): 59
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/pageObjects/common/LibraryNotification.js`, `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`
- out-of-scope edits: —

#### Condition: `glm:Pro/zai-org/GLM-5.1`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 6 [5–7]
- tokens: prompt=118262 / completion=8620 / total=126882
- cost_usd: 0.142446
- tool calls (total): 31
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/pageObjects/common/LibraryNotification.js`, `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 8 [7–9]
- tokens: prompt=222478 / completion=15557 / total=238035
- cost_usd: 0.170824
- tool calls (total): 41
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/pageObjects/common/LibraryNotification.js`, `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.5-397B-A17B`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 4 [4–7]
- tokens: prompt=108133 / completion=8555 / total=116688
- cost_usd: 0.087479
- tool calls (total): 23
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/pageObjects/common/LibraryNotification.js`, `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.6-35B-A3B`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 8 [5–11]
- tokens: prompt=213966 / completion=13805 / total=227771
- cost_usd: 0.064881
- tool calls (total): 40
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 1/5 oracle tests; failing: `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/pageObjects/common/LibraryNotification.js`, `tests/wdio/specs/regression/snapshot/snapshots/Snapshots_SendBackground.spec.js`
- out-of-scope edits: —

### Task: `f-f2`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 13 [12–21]
- tokens: prompt=622534 / completion=41554 / total=664088
- cost_usd: 1.227817
- tool calls (total): 82
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 2/4 oracle tests; failing: `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/wdio.conf.ts`
- out-of-scope edits: —

#### Condition: `glm:Pro/zai-org/GLM-5.1`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 200 [200–200] (5 right-censored at cap)
- tokens: prompt=9209253 / completion=47773 / total=9257026
- cost_usd: 9.172209
- tool calls (total): 1000
- safety-cap hits: 5
- dominant stop: safety_cap
- grader gap: passed 0/4 oracle tests; failing: `test::analyzeFailure result is captured into a variable`, `test::emits no failed-requests block when every request is 2XX`, `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: —
- out-of-scope edits: —

#### Condition: `minimax:MiniMax-M3`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 20 [10–55]
- tokens: prompt=770622 / completion=64979 / total=835601
- cost_usd: 0.618323
- tool calls (total): 119
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 2/4 oracle tests; failing: `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/wdio.conf.ts`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.5-397B-A17B`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 119 [5–162]
- tokens: prompt=4925138 / completion=44688 / total=4969826
- cost_usd: 2.811514
- tool calls (total): 453
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 2/4 oracle tests; failing: `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/wdio.conf.ts`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.6-35B-A3B`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 11 [6–27]
- tokens: prompt=406258 / completion=25553 / total=431811
- cost_usd: 0.122136
- tool calls (total): 64
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 0/4 oracle tests; failing: `test::analyzeFailure result is captured into a variable`, `test::emits no failed-requests block when every request is 2XX`, `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/utils/failure-analysis/index.ts`, `tests/wdio/utils/failure-analysis/types.ts`, `tests/wdio/wdio.conf.ts`
- out-of-scope edits: `tests/wdio/utils/failure-analysis/index.ts`, `tests/wdio/utils/failure-analysis/types.ts`

### Task: `f-f3`

#### Condition: `deepseek:deepseek-v4-pro`

- pass: 2/5 — ✅❌❌❌✅
- rounds: 5 [3–6]
- tokens: prompt=133671 / completion=9237 / total=142908
- cost_usd: 0.264732
- tool calls (total): 20
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 34/35 oracle tests; failing: `test::network attachment caps the line count and summarizes the rest`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/utils/failure-analysis/report-to-allure.js`
- out-of-scope edits: —

#### Condition: `glm:Pro/zai-org/GLM-5.1`

administrative 0/5 — not executed (owner decision)

#### Condition: `minimax:MiniMax-M3`

- pass: 0/5 — ❌❌❌❌❌
- rounds: 18 [13–24]
- tokens: prompt=740425 / completion=24430 / total=764855
- cost_usd: 0.502887
- tool calls (total): 89
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 34/35 oracle tests; failing: `test::network attachment caps the line count and summarizes the rest`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/utils/failure-analysis/report-to-allure.js`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.5-397B-A17B`

- pass: 3/5 — ❌✅✅❌✅
- rounds: 3 [3–3]
- tokens: prompt=62076 / completion=5005 / total=67081
- cost_usd: 0.050538
- tool calls (total): 10
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 34/35 oracle tests; failing: `test::network attachment caps the line count and summarizes the rest`
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/utils/failure-analysis/report-to-allure.js`
- out-of-scope edits: —

#### Condition: `siliconflow:Qwen/Qwen3.6-35B-A3B`

- pass: 5/5 — ✅✅✅✅✅
- rounds: 3 [3–16]
- tokens: prompt=191805 / completion=11217 / total=203022
- cost_usd: 0.056308
- tool calls (total): 27
- safety-cap hits: 0
- dominant stop: completed_natural
- grader gap: passed 35/35 oracle tests; failing: none
- displaced (oracle overlay): `tests/wdio/package.json`
- edited: `tests/wdio/utils/failure-analysis/report-to-allure.js`
- out-of-scope edits: —

## Task-defect candidates

Tasks that every non-blocked condition with records unanimously fails. Flagged for human review, never auto-classified (ADR-0013).

- `f-f1` (5 conditions, 25 runs)
  - shared failing oracle unit(s): `test::TC99396_10 waits on the named terminal snapshot notification`, `test::page-object wait resolves on a READY-only terminal state`, `test::page-object wait resolves on an ERROR-only terminal state`, `test::page-object wait throws when NEITHER terminal notification ever appears`
- `f-f2` (5 conditions, 25 runs)
  - shared failing oracle unit(s): `test::logs failed (non-2XX) requests and omits 2XX`, `test::logs the engine signal and confidence`

## Per-condition efficiency

| condition | rounds median [min–max] | prompt tok | completion tok | total tok | cost (USD) | tool calls | safety-cap hits | max-rounds hits | dominant stop |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek:deepseek-v4-pro | 9 [3–21] | 1086928 | 73185 | 1160113 | 2.1459 | 161 | 0 | 0 | completed_natural |
| glm:Pro/zai-org/GLM-5.1 | 103.5 [5–200] (5 right-censored at cap) | 9327515 | 56393 | 9383908 | 9.3147 | 1031 | 5 | 0 | completed_natural |
| minimax:MiniMax-M3 | 16 [7–55] | 1733525 | 104966 | 1838491 | 1.2920 | 249 | 0 | 0 | completed_natural |
| siliconflow:Qwen/Qwen3.5-397B-A17B | 4 [3–162] | 5095347 | 58248 | 5153595 | 2.9495 | 486 | 0 | 0 | completed_natural |
| siliconflow:Qwen/Qwen3.6-35B-A3B | 8 [3–27] | 812029 | 50575 | 862604 | 0.2433 | 131 | 0 | 0 | completed_natural |

## Failure classification (fc-v4) per task × condition

### `f-f1` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f1` × `glm:Pro/zai-org/GLM-5.1`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f1` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f1` × `siliconflow:Qwen/Qwen3.5-397B-A17B`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f1` × `siliconflow:Qwen/Qwen3.6-35B-A3B`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f2` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f2` × `glm:Pro/zai-org/GLM-5.1`

| category | subcategory |
| --- | --- |
| agent_failure | budget_exhausted |
| agent_failure | budget_exhausted |
| agent_failure | budget_exhausted |
| agent_failure | budget_exhausted |
| agent_failure | budget_exhausted |

### `f-f2` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f2` × `siliconflow:Qwen/Qwen3.5-397B-A17B`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f2` × `siliconflow:Qwen/Qwen3.6-35B-A3B`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f3` × `deepseek:deepseek-v4-pro`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f3` × `minimax:MiniMax-M3`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

### `f-f3` × `siliconflow:Qwen/Qwen3.5-397B-A17B`

| category | subcategory |
| --- | --- |
| agent_failure | oracle_red |
| agent_failure | oracle_red |

