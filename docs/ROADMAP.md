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

## Weeks 1-2: Minimum Evaluation System (tool-use slice)

Deliver:

- a locked `VerificationSpec` subset and task schema;
- a synthetic workspace-world with schema-validated tools;
- ~20 tool-use tasks (tool selection and argument extraction);
- a Python runner (OpenAI-compatible client, model↔tool loop, limits, multi-run
  from day one, cost capture);
- an AST tool-call grader with a structured failure taxonomy;
- an initial golden conformance suite;
- a baseline report.

Engineering focus:

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
