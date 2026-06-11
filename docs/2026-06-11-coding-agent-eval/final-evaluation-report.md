# Final evaluation report — coding-agent-eval (Weeks 5-6)

- Dataset: `code_repair_v1` · n=15 tasks · k=3 · bootstrap seed=20260610 · classifier fc-v2
- Conditions: C1=deepseek:deepseek-v4-pro (hosted, complete), C2=glm:Pro/zai-org/GLM-5.1 (hosted, complete), C3=minimax:MiniMax-M3 (hosted, complete), C4=local:Qwen/Qwen3-8B (local, complete)
- Temperature 0.0 was *requested*; no seed is sent and hosted providers are not greedy-deterministic at temp 0, so residual run-to-run variation is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob is the bootstrap RNG.

## Per-condition reliability

| condition | status | tasks | runs | pass@1 | pass^3 [95% CI] |
| --- | --- | --- | --- | --- | --- |
| C1 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |
| C2 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |
| C3 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |
| C4 | complete | 15 | 45 | 1.000 | 1.000 [1.000, 1.000] |

## Per-tier pass^3

| condition | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- |
| C1 | 1.000 | 1.000 | 1.000 | 1.000 |
| C2 | 1.000 | 1.000 | 1.000 | 1.000 |
| C3 | 1.000 | 1.000 | 1.000 | 1.000 |
| C4 | 1.000 | 1.000 | 1.000 | 1.000 |

## Per-capability pass^3

| condition | cross_file_repair | overfit_resistance | prose_localization | regression_preservation | test_comprehension | visible_test_localization |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| C2 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| C3 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| C4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

## Failure classification (fc-v2)

Derived at report time from the recorded mechanical discriminators; never stored on any record (ADR-0013).

### Harness defect found and fixed (fc-v1 → fc-v2)

The first C4 (local:Qwen/Qwen3-8B) capture recorded 39 failures (pass@1 0.133), 30 of them parse_failure runs that fc-v1 classified agent_failure/malformed_reply. Diagnosis showed an evaluation-system defect, not an agent limitation: the client sent no `max_tokens`, so each provider's default applied — the local MLX server defaults to 512 completion tokens, and Qwen3-8B (a thinking model) exhausted the whole budget inside its reasoning channel. 27 of the 30 runs show `completion_tokens == 512` exactly with neither content nor tool_calls (the other 3 hit the same per-request ceiling on a later turn). The fix made the completion budget an explicit eval parameter (`--max-tokens`, default 4096, recorded on every trajectory — never a provider default) and added the fc-v2 `token_budget_exhausted` subcategory so a budget-stopped reply is never again lumped with `malformed_reply`. Rerun under the explicit budget, C4 moved from pass@1 0.133 to 1.000; the superseded capture remains in git history. This reclassification — 30 "agent failures" that were actually one harness defect — is the clearest demonstration in this report of why the task/agent/harness split earns its keep.

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
| (no failures) | — | 0 |

Judgment-row footnotes:

- `tree_collision` → agent_failure: oracle paths are disjoint from every initial-tree path (ADR-0012's conformance contract) and code-world has no delete tool, so a canonical-prefix collision can only be minted by the run's own write; exact-path equality is displacement, never collision (ADR-0010). Conditional on the conformance contract, which holds for the code-repair lineage.
- `oracle_empty` → task_failure: conformance proves every shipped oracle collects ≥1 test and the overlay always contributes the oracle files (a collection-breaking agent write yields suite status `error`, pytest exit 2, never `no_tests`), so an empty oracle at grading time indicts the task data.
- `missing_final_state` → harness_failure: the runner always seeds final_state from initial_state, so its absence is a wiring defect.
- `step_exhaustion` outranks the oracle statuses: a budget-truncated attempt's red oracle is an artifact of the truncation, and the budget is data-validated (per-task metadata.max_steps via effective_max_steps, conformance-floored) — exhaustion is the agent's spend, not harness starvation.
- `malformed_reply` stays agent-side: message-level emptiness (assistant message with neither content nor tool_calls) means the provider envelope was well-formed and the model's own message was unparseable; only the empty-choices envelope (`provider_response`) is the harness's.
- `foreign_verdict` is the error-branch fallback: the evidence kind is an open string, so any unrecognized kind files as a harness verdict-plumbing fault, never an agent miss (grill Q1).
- fc design note (cr-007 vs cr-014, first C4 capture): classification reads the grade's evidence shape, never the trajectory surface — cr-007's red oracle arrived as the execution grader's own evidence while cr-014's arrived inside an all_of composite, walked to its first execution leg in declared order; both paths landed on agent_failure/oracle_red. A composite's failing non-execution leg is visible to fc only through grade.failure_reason (rows 10-11) — a design choice disclosed here, not an observed misclassification; both tasks pass every run in the post-fix rerun.

## Task-defect candidates

Task ids failing all recorded runs on every non-blocked condition with records for them — *flagged for human review*, never auto-classified: conformance already proves solvability, oracle breadth, and symptom reality, so unanimity defaults to "hard, not defective" pending adjudication.

none

## Cost and latency

Prices snapshot: 2026-06-11 (committed prices.json); conditions absent from the snapshot render as not computed. Latency is summed from recorded per-run `usage.latency_s`.

| condition | prompt tokens | completion tokens | cost (USD) | mean run latency (s) |
| --- | --- | --- | --- | --- |
| C1 | 258063 | 33544 | 0.1414 | 16.29 |
| C2 | 143739 | 14534 | 0.2652 | 24.78 |
| C3 | 287689 | 28788 | 0.1209 | 15.78 |
| C4 | 97905 | 102939 | not computed | 126.38 |

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
- No observed difference: C1 vs C3 — both conditions identical on this dataset (Δ 0.000).
- No observed difference: C2 vs C3 — both conditions identical on this dataset (Δ 0.000).
- n=15 honesty: intervals are wide; absence of a detectable separation is not evidence of no separation.

## Known limitations

- ADR-0010 residual trust boundary: the oracle suite imports agent-authored modules in-process, so import-time code in graded modules runs inside the sandbox process.
- Sandbox isolation is temp-dir-and-convention, not kernel-level: no containers, no per-test process isolation (001/002 non-goals).
- n=15 tasks, dev split only: intervals are wide and per-tier / per-capability cells are tiny.
- graders/policy.py dotted-path false-allow residual: an agent minting a fresh extension path at run time (e.g. writing `app.py.bak` under an `app.py` allowlist) is silently *passed* — a missed-detection bias the per-run classifier cannot see (003-spec criterion 16).
- pytest_edge cleanup is `shutil.rmtree(ignore_errors=True)`, so a sandbox dir can leak silently; a disk-full OSError mid-materialize is captured as an ExecutionError(kind="harness") by the oracle edge — the worked example of a `sandbox_fault` harness failure (001-review).
- Hosted providers are not greedy-deterministic at temperature 0; run-to-run variation is measured by k=3 + pass^3, never claimed away.
- `openrouter:gpt-5.5` is unreachable from this network (region / datacenter-IP ToS policy) — a network constraint, not a harness fault.
- Budget asymmetry: the C1/C2 runs predate the explicit completion budget — their requests sent no max_tokens, so each provider's (larger) default applied and no budget is recorded on those trajectories. With every C1/C2 run passing, the parameter was not binding, so they were not rerun; C3 and C4 were captured post-fix with max_tokens=4096 recorded on every trajectory.

## Roadmap takeaways

- The fc-v2 (category, subcategory) counts are the direct input to the Weeks 9-10 failure-mining work; downstream joins on (classifier_version, category, subcategory) (ADR-0013).
- Task-defect candidates are review-queue input, never auto-reclassified; an adjudicated defect ships as a future dataset version, never an edit (append-only).
- The per-tier and per-capability gradients feed the Weeks 9-10 hardness levers recorded in the Weeks 3-4 takeaways.
- The committed runs JSONLs embed agent solution trees and oracle output, so they join the Weeks 9-10 never-train manifest beside the review-fixtures sidecar.
- Under the corrected harness every reachable condition saturates code_repair_v1 (pass^3 = 1.000 across C1-C4) — the Weeks 3-4 lesson repeats: the next dataset version needs harder tiers. Levers for Weeks 9-10 / 13-14: deeper repair chains (chain depth), multi-file edits, oblique specs without visible tests, and larger n.

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
