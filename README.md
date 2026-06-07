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

```text
src/agent_eval_lab/
  graders/          Pure grading logic
tests/
  graders/          Unit tests for graders
examples/datasets/  Small example evaluation datasets
docs/
  ARCHITECTURE.md   Boundaries and design principles
  ROADMAP.md        Twelve-week delivery plan
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

## Twelve-Week Outcome

By the end of the initial roadmap, this repository should contain:

- a documented task taxonomy and versioned dataset;
- deterministic, execution-based, and model-based graders;
- a reproducible evaluation runner;
- trace inspection and failure-mode analysis;
- at least two controlled comparison experiments;
- a portfolio-quality technical report.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the delivery plan.

## Status

This repository is at the foundation stage. The current implementation begins
with a pure exact-match grader and its tests.

## License

MIT
