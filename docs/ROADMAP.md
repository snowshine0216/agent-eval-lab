# Sixteen-Week Roadmap

The roadmap prioritizes job-relevant Agent Evaluation evidence first, then dataset
engineering, then finetuning. Software architecture, functional programming,
testing, and statistics are learned by applying them to the project rather than
studying them in isolation.

It ships as two independent portfolio releases so that finetuning never delays the
evaluation system:

- **Release #1 — Evaluation portfolio (Weeks 1–12).** No training dependency.
- **Release #2 — Data and finetuning (Weeks 13–16).**

Full design and rationale:
[superpowers/specs/2026-06-09-agent-eval-pipeline-design.md](superpowers/specs/2026-06-09-agent-eval-pipeline-design.md).

## Time Allocation

- 65%: build and analyze Agent Evaluation systems;
- 25%: apply software engineering fundamentals;
- 10%: build statistical foundations.

## Weeks 1-2: Minimum Evaluation System (tool-use slice) — ✅ delivered

**Status: implemented and merged to `main` (2026-06-10, via #4); first baseline
numbers captured 2026-06-10.** Harness gates are green (130 tests; `ruff check` /
`ruff format` clean). The `run-baseline` command has been exercised end-to-end
against four live model endpoints — three hosted providers and a local MLX server.

Delivered:

- ✅ a locked `VerificationSpec` subset (`OutputMatchSpec | ToolCallMatchSpec`)
  and task schema with a JSONL loader;
- ✅ a synthetic workspace-world with three schema-validated tools
  (`search_docs`, `create_ticket`, `update_ticket`), where world and grader
  share one validator;
- ✅ a 20-task tool-use dataset (tool selection, argument extraction, multi-step);
- ✅ a Python runner — OpenAI-compatible client with a six-provider registry,
  model↔tool loop, step limits, multi-run from day one, and cost capture;
- ✅ an AST tool-call grader with a structured failure taxonomy (`malformed_call`,
  `schema_violation`, `wrong_tool`, `wrong_args`, `missing_call`, `extra_call`,
  `order_mismatch`);
- ✅ a golden conformance suite (11 hand-verified trajectories) plus Hypothesis
  property tests;
- ✅ the `run-baseline` report command (pure build + markdown render).

Baseline results (`workspace_tool_use_v1`, k=3 → 60 runs/condition; full write-up
in `reports/overview.md`, gitignored):

| condition | pass@1 | pass^3 | failures |
| --- | --- | --- | --- |
| `deepseek:deepseek-v4-pro` | 1.000 | 1.000 | — |
| `glm:Pro/zai-org/GLM-5.1` (SiliconFlow) | 1.000 | 1.000 | — |
| `minimax:MiniMax-M3` | 1.000 | 1.000 | — |
| `local:Qwen3-8B` (MLX) | 0.900 | 0.900 | `extra_call` ×6 |
| `openrouter:openai/gpt-5.5` | — | — | blocked (region / datacenter-IP ToS) |

The three hosted frontier models are perfect on the v1 set — it separates them
only on cost and latency, not accuracy. The signal is **local Qwen3-8B**, which
fails `ws-017`/`ws-018` (both multi-step) *deterministically* across all 3 runs by
appending a redundant `update_ticket` — a reproducible over-calling failure mode,
not variance. `openrouter:gpt-5.5` is unreachable from this network (China
region-block when direct; the available proxy exits a ToS-flagged datacenter
subnet) — the proxy wiring is correct (open models route through it fine), only
premium providers reject the IP.

Takeaway for Weeks 3-4: the v1 set saturates frontier accuracy, confirming the
need for harder tasks and a model-based grader to separate strong configurations.

Engineering focus (applied):

- dependency boundaries;
- pure core and effectful edges;
- actions, calculations, and data.

## Weeks 3-4: Dataset and Grader Quality

Deliver:

- a task taxonomy and scoring rubric;
- 50 reviewed tasks;
- final-state and composite (`AllOf` / `TrajectorySpec`) verification;
- an initial model-based grader with calibration (Cohen's κ, ≥2 annotators);
- a failure-mode report;
- a comparison of two agent configurations.

Statistics focus:

- probability and random variables;
- expectation and variance;
- estimators and confidence intervals.

## Weeks 5-6: Coding Agent Evaluation

Deliver:

- 10-20 small code-repair tasks;
- execution-based graders (tests as the oracle);
- isolated, reproducible task environments;
- explicit classification of task, agent, and harness failures.

Engineering focus:

- test-driven development;
- boundary and integration testing;
- reproducibility.

## Weeks 7-8: Controlled Experiments

Run two pre-specified experiments:

> E1: Does a more precise tool description improve tool-selection accuracy?
> E2: Which model is most reliable (`pass^3`) at argument extraction, at what cost?

Deliver:

- hypothesis and metric definitions (`ExperimentSpec`);
- development and held-out splits;
- repeated trials with cluster-bootstrap confidence intervals;
- multiple-testing control (Holm / Bonferroni);
- trace-based failure analysis;
- an Inspect AI harness conformance check.

Statistics focus:

- hypothesis testing;
- bootstrap confidence intervals;
- regression fundamentals;
- multiple-testing risk.

## Weeks 9-10: Multi-Turn Failure Modes and Leakage-Safe Splits

Add tasks for:

- incorrect tool selection;
- incorrect argument extraction;
- premature termination;
- repeated or looping actions;
- forgotten earlier instructions;
- failure recovery;
- grader exploitation.

Deliver:

- a deterministic scripted-user protocol for multi-turn tasks;
- failure mining from traces into new hard tasks;
- leakage-safe splits (isolation by `world_template_id` and seed family) and a
  never-train manifest;
- a report distinguishing agent limitations from evaluation-system defects.

## Weeks 11-12: Portfolio Release #1 (Evaluation)

Deliver:

- a clear README and architecture diagram;
- dataset documentation;
- reproducible experiment commands;
- CI and automated tests;
- two controlled experiments;
- a failure-mode analysis;
- known limitations;
- a technical article in English or Chinese.

This release has no training dependency.

## Weeks 13-14: Dataset Engineering

Deliver:

- a synthetic task generator with parametrized difficulty;
- append-only dataset versions with minimal dataset cards;
- three contamination checks (internal leakage, template overlap, optional
  public-benchmark similarity);
- one curated SFT dataset and a `TrajectoryExample` export format with round-trip
  tests into the local inference client.

## Weeks 15-16: Portfolio Release #2 (Finetuning, MLX)

Deliver:

- one SFT / LoRA adapter on Qwen3-8B via MLX (`mlx-lm`);
- closed-loop re-evaluation against the base model in the Phase-1 harness, on the
  frozen held-out split, with bootstrap confidence intervals;
- a capability-regression matrix (controllability detection).

Stretch (only if Phase 2 finishes early): DPO on matched preference pairs; a
two-strategy annotation experiment; agent reinforcement learning (GRPO, rented
GPU).

## Reading Applied to the Project

- *Clean Architecture*: boundaries and dependency direction;
- *Grokking Simplicity*: pure calculations, actions, and immutable data;
- *Test-Driven Development by Example*: red-green-refactor delivery;
- *All of Statistics*: uncertainty and experimental reasoning;
- *AI Engineering* (Huyen): evaluation methodology, dataset engineering, finetuning.

*Advances in Financial Machine Learning* and *Fundamentals of Software
Architecture* are intentionally deferred until the initial portfolio milestone is
complete.
