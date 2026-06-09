# Agent Eval Lab

Agent Eval Lab is a portfolio-driven learning project for designing, running,
and analyzing reproducible evaluations of AI agents.

The project turns agent evaluation concepts into working evidence:

- versioned evaluation datasets;
- isolated and reproducible runs;
- deterministic and model-based graders;
- trace-level failure analysis;
- comparisons across models, prompts, tools, and agent configurations;
- explicit reporting of quality, cost, latency, and reliability.

## Why This Repository Exists

Agent systems are difficult to evaluate because they make decisions over
multiple turns, call tools, modify state, and may reach valid outcomes through
different paths. A useful evaluation system must distinguish:

- agent failures from harness failures;
- genuine improvements from experimental noise;
- task completion from grader exploitation;
- development-set progress from held-out generalization.

This repository is both a learning environment and a public portfolio artifact.
It aims to demonstrate the ability to build evaluation datasets, implement
reliable evaluation infrastructure, analyze failures, and communicate results.

## Initial Scope

The first milestone focuses on a small, trustworthy evaluation core:

1. Define a versioned task schema.
2. Implement pure, deterministic graders.
3. Keep model calls, file access, and process execution at explicit I/O edges.
4. Record run results and traces as data.
5. Produce a baseline report before adding system complexity.

The project deliberately starts with deterministic graders before introducing
LLM-as-judge evaluation.

## Quick Start

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Repository Layout

Target layout (the current checkout is at the foundation stage — see Status):

```text
src/agent_eval_lab/
  tasks/            Task schema and validation
  tools/            Synthetic tool-world (schemas + pure implementations)
  runners/          Model<->tool loop and trace capture (I/O edge)
  graders/          Pure tiered grading logic
  metrics/          Pure aggregation (pass@k, pass^k, bootstrap CIs)
  reports/          Report models and rendering
  experiments/      Pre-registered experiment specs and analysis
tests/              Unit, integration, and golden-conformance tests
examples/datasets/  Small example evaluation datasets
docs/
  ARCHITECTURE.md       Boundaries and design principles
  ROADMAP.md            Sixteen-week delivery plan
  superpowers/specs/    Detailed design documents
```

## Engineering Principles

- Use test-driven development: red, green, refactor.
- Keep deterministic transformations pure.
- Pass dependencies and data explicitly.
- Treat datasets, traces, metrics, and usage as immutable records.
- Isolate external effects at the edges.
- Prefer small modules and composable functions.
- Make experimental assumptions and limitations visible.

## Evaluation Principles

- Start with representative tasks and a clearly defined capability boundary.
- Use stable, isolated environments for each trial.
- Combine grader types only when each one has a clear purpose.
- Calibrate model-based graders against human judgments.
- Read traces to verify that failures are fair and informative.
- Preserve a held-out set for final evaluation.
- Report uncertainty, failure modes, and known limitations.

## Outcomes

The roadmap ships as two independent portfolio releases, so finetuning never
delays the evaluation system.

**Release #1 — Evaluation portfolio (Weeks 1–12), no training dependency:**

- a documented task taxonomy and versioned dataset;
- deterministic, execution-based, and calibrated model-based graders;
- a reproducible, multi-run runner reporting cost and reliability (`pass^k`);
- trace inspection and failure-mode analysis;
- two pre-registered controlled experiments with bootstrap confidence intervals;
- a golden conformance suite cross-checked against Inspect AI;
- a portfolio-quality technical report.

**Release #2 — Data and finetuning (Weeks 13–16):**

- a synthetic task generator and a curated SFT dataset with dataset cards;
- one MLX-finetuned model re-evaluated in this harness — the "my data → my model
  → my eval" closed loop — with a capability-regression matrix.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the delivery plan and
[docs/superpowers/specs/](docs/superpowers/specs/) for the detailed design.

## Status

This repository is at the foundation stage. The current implementation begins
with a pure exact-match grader and its tests; the full pipeline is specified in
[docs/superpowers/specs/](docs/superpowers/specs/) and built slice by slice.

## License

MIT
