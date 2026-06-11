# Final evaluation report — coding-agent-eval (Weeks 5-6)

- Dataset: `code_repair_v1` · n=15 tasks · k=3 · bootstrap seed=20260610 · classifier fc-v1
- Conditions: C1=deepseek:deepseek-v4-pro (hosted, complete), C2=glm:Pro/zai-org/GLM-5.1 (hosted, complete), C3=minimax:MiniMax-M3 (hosted, incomplete), C4=local:Qwen/Qwen3-8B (local, complete)
- Temperature 0.0 was *requested*; no seed is sent and hosted providers are not greedy-deterministic at temp 0, so residual run-to-run variation is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob is the bootstrap RNG.

## Per-condition reliability

| condition | status | tasks | runs | pass@1 | pass^3 [95% CI] |
| --- | --- | --- | --- | --- | --- |
| C1 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |
| C2 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |
| C3 | incomplete | 2 | 6 | 1.000 | 1.000 [1.000, 1.000] |
| C4 | complete | 15 | 45 | 0.133 | 0.133 [0.000, 0.333] |

## Per-tier pass^3

| condition | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- |
| C1 | 1.000 | 1.000 | 1.000 | 1.000 |
| C2 | 1.000 | 1.000 | 1.000 | 1.000 |
| C3 | 1.000 | — | — | — |
| C4 | 0.500 | 0.000 | 0.167 | 0.000 |

## Per-capability pass^3

| condition | cross_file_repair | overfit_resistance | prose_localization | regression_preservation | test_comprehension | visible_test_localization |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| C2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| C3 | — | — | — | — | — | 1.000 |
| C4 | 0.000 | 0.000 | 0.500 | 0.000 | 0.000 | 0.250 |

## Failure classification (fc-v1)

Derived at report time from the recorded mechanical discriminators; never stored on any record (ADR-0013).

### C1 (deepseek:deepseek-v4-pro)

| category | subcategory | count |
| --- | --- | --- |
| (no failures) | — | 0 |

### C2 (glm:Pro/zai-org/GLM-5.1)

| category | subcategory | count |
| --- | --- | --- |
| (no failures) | — | 0 |

### C3 (minimax:MiniMax-M3)

| category | subcategory | count |
| --- | --- | --- |
| (no failures) | — | 0 |

### C4 (local:Qwen/Qwen3-8B)

| category | subcategory | count |
| --- | --- | --- |
| agent_failure | malformed_reply | 30 |
| agent_failure | oracle_red | 9 |

Exemplars (deterministic: lex-first task id, lowest run_index):
- **agent_failure/malformed_reply** — task `cr-001`, run 0: parse_failure: assistant message has neither content nor tool_calls

Judgment-row footnotes:

- `tree_collision` → agent_failure: oracle paths are disjoint from every initial-tree path (ADR-0012's conformance contract) and code-world has no delete tool, so a canonical-prefix collision can only be minted by the run's own write; exact-path equality is displacement, never collision (ADR-0010). Conditional on the conformance contract, which holds for the code-repair lineage.
- `oracle_empty` → task_failure: conformance proves every shipped oracle collects ≥1 test and the overlay always contributes the oracle files (a collection-breaking agent write yields suite status `error`, pytest exit 2, never `no_tests`), so an empty oracle at grading time indicts the task data.
- `missing_final_state` → harness_failure: the runner always seeds final_state from initial_state, so its absence is a wiring defect.
- `step_exhaustion` outranks the oracle statuses: a budget-truncated attempt's red oracle is an artifact of the truncation, and the budget is data-validated (per-task metadata.max_steps via effective_max_steps, conformance-floored) — exhaustion is the agent's spend, not harness starvation.
- `malformed_reply` stays agent-side: message-level emptiness (assistant message with neither content nor tool_calls) means the provider envelope was well-formed and the model's own message was unparseable; only the empty-choices envelope (`provider_response`) is the harness's.
- `foreign_verdict` is the error-branch fallback: the evidence kind is an open string, so any unrecognized kind files as a harness verdict-plumbing fault, never an agent miss (grill Q1).

## Task-defect candidates

Task ids failing all recorded runs on every non-blocked condition with records for them — *flagged for human review*, never auto-classified: conformance already proves solvability, oracle breadth, and symptom reality, so unanimity defaults to "hard, not defective" pending adjudication.

none

## Cost and latency

Prices snapshot: 2026-06-11 (committed prices.json); conditions absent from the snapshot render as not computed. Latency is summed from recorded per-run `usage.latency_s`.

| condition | prompt tokens | completion tokens | cost (USD) | mean run latency (s) |
| --- | --- | --- | --- | --- |
| C1 | 258063 | 33544 | 0.1414 | 16.29 |
| C2 | 143739 | 14534 | 0.2652 | 24.78 |
| C3 | 36331 | 2849 | 0.0143 | 13.19 |
| C4 | 35901 | 31731 | not computed | 38.92 |

## Context: prior baselines (workspace_tool_use v1/v2)

The same four conditions were baselined on the workspace worlds in Weeks 1-4
(committed reports: docs/2026-06-10-dataset-grader-quality/).

- `workspace_tool_use_v1` (20 tasks, 3 tools) saturated: hosted conditions at
  pass^3 = 1.000 - it separated models on cost and latency only.
- `workspace_tool_use_v2` (50 tasks, k=3, the same bootstrap conventions):

| condition | pass@1 | pass^3 [95% CI] |
| --- | --- | --- |
| C1 deepseek:deepseek-v4-pro | 1.000 | 1.000 [1.000, 1.000] |
| C2 glm:Pro/zai-org/GLM-5.1 | 1.000 | 1.000 [1.000, 1.000] |
| C3 minimax:MiniMax-M3 | 0.980 | 0.940 [0.860, 1.000] |
| C4 local:Qwen/Qwen3-8B | 0.620 | 0.620 [0.480, 0.740] |

v2 discriminativeness verdict: weak rung (hosted separation within noise at
n=50); the local condition separated decisively, with T3 its hardest tier
(pass^3 0.318).

Cross-dataset numbers are *context*, never a paired statistic: the task universes differ, so no CI is computed across them.

## Discriminativeness verdict

- Rung met: **none** (weak=False, strong=False) — the Weeks 3-4 mechanical rule, reused unchanged.
- No observed difference: C1 vs C2 — both conditions identical on this dataset (Δ 0.000).
- Skipped pair: C1 vs C3 — universe mismatch (task-id sets differ; paired CI requires identical universe).
- Skipped pair: C2 vs C3 — universe mismatch (task-id sets differ; paired CI requires identical universe).
- n=15 honesty: intervals are wide; absence of a detectable separation is not evidence of no separation.

## Known limitations

- ADR-0010 residual trust boundary: the oracle suite imports agent-authored modules in-process, so import-time code in graded modules runs inside the sandbox process.
- Sandbox isolation is temp-dir-and-convention, not kernel-level: no containers, no per-test process isolation (001/002 non-goals).
- n=15 tasks, dev split only: intervals are wide and per-tier / per-capability cells are tiny.
- graders/policy.py dotted-path false-allow residual: an agent minting a fresh extension path at run time (e.g. writing `app.py.bak` under an `app.py` allowlist) is silently *passed* — a missed-detection bias the per-run classifier cannot see (003-spec criterion 16).
- pytest_edge cleanup is `shutil.rmtree(ignore_errors=True)`, so a sandbox dir can leak silently; a disk-full OSError mid-materialize is captured as an ExecutionError(kind="harness") by the oracle edge — the worked example of a `sandbox_fault` harness failure (001-review).
- Hosted providers are not greedy-deterministic at temperature 0; run-to-run variation is measured by k=3 + pass^3, never claimed away.
- `openrouter:gpt-5.5` is unreachable from this network (region / datacenter-IP ToS policy) — a network constraint, not a harness fault.
- Condition C3 is incomplete (2/15 tasks at full k); pass^k covers only its complete tasks.

## Roadmap takeaways

- The fc-v1 (category, subcategory) counts are the direct input to the Weeks 9-10 failure-mining work; downstream joins on (classifier_version, category, subcategory) (ADR-0013).
- Task-defect candidates are review-queue input, never auto-reclassified; an adjudicated defect ships as a future dataset version, never an edit (append-only).
- The per-tier and per-capability gradients feed the Weeks 9-10 hardness levers recorded in the Weeks 3-4 takeaways.
- The committed runs JSONLs embed agent solution trees and oracle output, so they join the Weeks 9-10 never-train manifest beside the review-fixtures sidecar.

## Excluded conditions

- `openrouter:openai/gpt-5.5` — unreachable by network policy: direct access is region-blocked from this network and the datacenter-IP proxy route is ToS-blocked (docs/ROADMAP.md) — a network constraint, not a harness fault

---

Regenerate byte-identically from the committed artifacts with:

```
uv run python -m agent_eval_lab.cli report-final \
  --runs \
    C1=deepseek:deepseek-v4-pro=docs/2026-06-11-coding-agent-eval/runs/runs-deepseek-deepseek-v4-pro.jsonl \
    C2=glm:Pro/zai-org/GLM-5.1=docs/2026-06-11-coding-agent-eval/runs/runs-glm-Pro-zai-org-GLM-5.1.jsonl \
    C3=minimax:MiniMax-M3=docs/2026-06-11-coding-agent-eval/runs/runs-minimax-MiniMax-M3.jsonl \
    C4=local:Qwen/Qwen3-8B=docs/2026-06-11-coding-agent-eval/runs/runs-local-Qwen-Qwen3-8B.jsonl \
  --dataset examples/datasets/code_repair_v1.jsonl \
  --tiers examples/datasets/code_repair_v1_tiers.json \
  --prices docs/2026-06-11-coding-agent-eval/prices.json \
  --context-file docs/2026-06-11-coding-agent-eval/v2-context.md \
  --k 3 --expected-n-tasks 15 --seed 20260610 --n-resamples 2000 --alpha 0.05 \
  --out docs/2026-06-11-coding-agent-eval/final-evaluation-report.md
```
