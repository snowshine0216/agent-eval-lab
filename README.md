# Agent Eval Lab

Agent Eval Lab is a laboratory for designing, running, and analyzing
reproducible evaluations of AI agents.

It provides, as working code:

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

This repository makes those distinctions mechanical rather than anecdotal:
versioned datasets, deterministic graders backed by a golden conformance suite,
calibrated model-based judging, and statistical reporting designed so that a
claimed improvement survives scrutiny.

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
- Node.js 18+ and npm — required for browser-based eval (Weeks 7–10)
- [`playwright-cli`](https://github.com/microsoft/playwright-cli) — browser automation for D-set and B-set tasks

```bash
uv sync --dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

### Browser-based eval prerequisites (Weeks 7–10)

Install `playwright-cli` once before running any D-set or B-set eval:

```bash
npm install -g @playwright/cli@latest
playwright-cli install --skills   # loads browser interaction skills into agent context
```

Run the environment preflight check before starting an eval session — it verifies
`playwright-cli` is installed and the MSTR environment is reachable:

```bash
uv run python -m agent_eval_lab.cli check-env
```

A passing preflight prints the `playwright-cli` version, confirms the MSTR
auth-login probe returned 2XX/3XX, and exits 0. Any failure exits non-zero with a
diagnostic message — do not start an eval session until `check-env` passes.

Run the tool-use baseline against any configured provider:

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/workspace_tool_use_v1.jsonl \
  --provider deepseek --k 3
```

Outputs land in `reports/` (gitignored): `baseline-<condition>.md` (headline
`pass@1`, `pass^k`, tokens, latency, failure taxonomy) and `runs-<condition>.jsonl`
(full graded trajectories, streamed per task). Artifacts are named by the full
condition id (`provider:model`) so two models under one provider never overwrite
each other. Pass `--input-price-per-mtok`/`--output-price-per-mtok` together to
include estimated cost.

### Providers

The registry lives in
[`src/agent_eval_lab/runners/config.py`](src/agent_eval_lab/runners/config.py).
Each hosted provider reads its key from the named environment variable (the code
stores the *name*, never the key):

| `--provider` | endpoint | default model | key env var |
| --- | --- | --- | --- |
| `deepseek`   | `api.deepseek.com`                | `deepseek-v4-pro`     | `DEEPSEEK_API_KEY` |
| `glm`        | `api.siliconflow.cn` (SiliconFlow) | `Pro/zai-org/GLM-5.1` | `SILICONFLOW_API_KEY` |
| `minimax`    | `api.minimaxi.com`                | `MiniMax-M3`          | `MINIMAX_API_KEY` |
| `openrouter` | `openrouter.ai` (via proxy)       | `openai/gpt-5.5`      | `OPENROUTER_API_KEY` |
| `local`      | `localhost:11434` (MLX / Ollama)  | `qwen3-8b`            | — (none) |

Set keys in your shell (`export DEEPSEEK_API_KEY=...`) or keep them in a `.env` and
`set -a; . .env; set +a` before running — there is **no** automatic `.env` loading.
Override a provider's default model with `--model <id>`.

**Proxy:** `openrouter` is routed through an HTTP proxy whose URL is read from the
`HTTP_PROXY` environment variable and applied **only** to `openrouter` — domestic
endpoints and `localhost` always stay direct. Set it with your proxy, e.g.
`export HTTP_PROXY=http://10.23.37.244:8888`; if unset, the call goes direct.

### Local model (Apple Silicon, MLX)

The `local` provider expects an OpenAI-compatible server on
`http://localhost:11434/v1`. With [`mlx-lm`](https://github.com/ml-explore/mlx-lm)
on an Apple-Silicon Mac:

```bash
uv pip install mlx-lm
# Serve Qwen3-8B on the port the `local` config expects.
# HF_HUB_OFFLINE=1 uses the local Hugging Face cache (no download).
HF_HUB_OFFLINE=1 uv run python -m mlx_lm.server \
  --model Qwen/Qwen3-8B --port 11434 --host 127.0.0.1
```

Then run the baseline against it, matching `--model` to the id the server loaded:

```bash
uv run python -m agent_eval_lab.cli run-baseline \
  --dataset examples/datasets/workspace_tool_use_v1.jsonl \
  --provider local --model Qwen/Qwen3-8B --k 3
```

`mlx_lm.server` emits OpenAI-format `tool_calls` for Qwen3, so the AST grader
scores local runs exactly as it scores hosted ones. (Ollama also works: `ollama
pull qwen3:8b` serves `:11434` automatically — then pass `--model qwen3:8b`.)

### Additional subcommands

`run-baseline` honors each task's `metadata.max_steps` (the `--max-steps` flag
is the fallback for tasks without one), sends an explicit completion budget via
`--max-tokens` (default 4096 — always passed to the provider, never left to its
default, so the trajectory records it for fc-v2 failure classification), and
accepts `--system-prompt-file <path>` to evaluate an alternate agent
configuration; tagged artifacts (`runs-<condition>__<tag>.jsonl`) keep two
configs of one model from overwriting each other.

```bash
# Rebuild the multi-condition validation / failure-mode report (pure, no
# live calls — deterministic for a fixed seed) from captured run JSONL:
uv run python -m agent_eval_lab.cli report-validation \
  --runs "C1=deepseek:deepseek-v4-pro=reports/runs-deepseek-deepseek-v4-pro.jsonl" \
  --dataset examples/datasets/workspace_tool_use_v2.jsonl \
  --tiers examples/datasets/workspace_tool_use_v2_tiers.json \
  --k 3 --expected-n-tasks 50 --seed 20260610 --n-resamples 2000 \
  --out reports/validation.md

# Compare two agent configurations of the same model (paired
# cluster-bootstrap Δ pass^3 with a pre-declared decision rule):
uv run python -m agent_eval_lab.cli compare-configs \
  --config-a reports/runs-deepseek-deepseek-v4-pro.jsonl \
  --config-b reports/runs-deepseek-deepseek-v4-pro__planning-v1.jsonl \
  --tiers examples/datasets/workspace_tool_use_v2_tiers.json \
  --planning-prompt-file examples/prompts/planning-v1.txt \
  --k 3 --seed 20260610 --n-resamples 2000 --out reports/comparison.md

# LLM-judge calibration workflow (blind annotation packets, Cohen's κ +
# bootstrap CI; see docs/2026-06-10-dataset-grader-quality/calibration-runbook.md):
uv run python -m agent_eval_lab.cli calibrate export-packet --out packet.jsonl
uv run python -m agent_eval_lab.cli calibrate provisional-label ...
uv run python -m agent_eval_lab.cli calibrate compute ...
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

The roadmap ships as two independent releases, so finetuning never
delays the evaluation system.

**Release #1 — Evaluation system (Weeks 1–12), no training dependency:**

- a documented task taxonomy and versioned dataset;
- deterministic, execution-based, and calibrated model-based graders;
- a reproducible, multi-run runner reporting cost and reliability (`pass^k`);
- trace inspection and failure-mode analysis;
- two pre-registered controlled experiments with bootstrap confidence intervals;
- a golden conformance suite cross-checked against Inspect AI;
- a publication-quality technical report.

**Release #2 — Data and finetuning (Weeks 13–16):**

- a synthetic task generator and a curated SFT dataset with dataset cards;
- one MLX-finetuned model re-evaluated in this harness — the "my data → my model
  → my eval" closed loop — with a capability-regression matrix.

See [docs/ROADMAP.md](docs/ROADMAP.md) for the delivery plan and
[docs/superpowers/specs/](docs/superpowers/specs/) for the detailed design.

## Status

Weeks 1–4 are implemented. Weeks 1–2 delivered the tool-use slice: locked
record types, a schema-validated workspace-world, the AST tool-call grader
with a structured failure taxonomy, a multi-run runner with cost capture, a
20-task dataset, a golden conformance suite, and the baseline report command.
Weeks 3–4 added composite verification (`FinalStateSpec`/`TrajectorySpec`/
`AllOf`), a 50-task capability-discriminating dataset with a conformance
suite, a calibrated-by-protocol LLM judge (provisional LLM–LLM κ; human
calibration packet ready), per-task step budgets, and live multi-condition
validation with failure-mode and two-config comparison reports. The full
pipeline is specified in [docs/superpowers/specs/](docs/superpowers/specs/)
and built slice by slice.

## License

MIT
