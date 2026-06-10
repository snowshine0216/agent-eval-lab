# Architecture

Agent Eval Lab uses a functional-core, imperative-shell architecture. This file
is the stable orientation; the full design and rationale live in
[superpowers/specs/2026-06-09-agent-eval-pipeline-design.md](superpowers/specs/2026-06-09-agent-eval-pipeline-design.md).

## Data Flow

```text
Task (initial_state + VerificationSpec)
      |
      v
Agent Runner (I/O edge) --- model<->tool loop ---> Trajectory (turns, usage, cost, run_index)
      |                                                   |
      v                                                   v
Pure Graders (tiered) -----------------------------> GradeResult (passed, evidence, failure_reason)
      |                                                   |
      v                                                   v
Pure Metrics (pass@k, pass^k, cost, bootstrap CIs) -> ExperimentResult
```

## Functional Core

Deterministic transformations:

- validate task data;
- interpret `VerificationSpec` and constraints to grade outputs, tool calls, and
  final state;
- aggregate metrics (pass@k, pass^k task-level reliability, cost/latency,
  bootstrap CIs);
- classify failures;
- compare conditions for pre-registered experiments.

Core functions must not perform network calls, process execution, file access,
logging, or mutation of caller-owned data. Records are immutable, serializable
data; behavior lives in pure functions, not on the records.

## Effectful Edges

- invoke models/agents through one OpenAI-compatible client — native dedicated
  keys per provider (DeepSeek, GLM, MiniMax, Qwen), OpenRouter as the gateway for
  the rest, an optional per-provider adapter normalizing tool-call dialects;
- execute tools and tests; thread synthetic-world state explicitly via
  `apply(tool, args, state) -> (state', result)`;
- read and write datasets; persist traces and reports.

Edges return explicit data passed into the core. **Types detect spec deviation;
the runner enforces it** (uses pre-registered seeds, computes only the planned
comparisons).

## Module Boundaries

```text
agent_eval_lab/
  tasks/        Task schema + validation (pure) · dataset loaders (edge)
  tools/        Synthetic tool-world: JSON schemas + pure implementations over explicit state
  runners/      Imperative shell: provider client, model<->tool loop, limits -> Trajectory
  graders/      Pure tiered scorers: output / tool-call (AST, schema-first) / state / trajectory / execution / judge
  metrics/      Pure aggregation: pass@k, pass^k, cost/latency, bootstrap CIs
  reports/      Pure report models + rendering · file I/O (edge)
  experiments/  ExperimentSpec/Result + analysis (pure) · orchestration (edge)
  data/         (Phase 2) generators, flywheel mining, dataset cards
  finetune/     (Phase 3) TrajectoryExample export, MLX SFT, closed-loop re-eval
```

Each module exposes a small public interface, stays focused, and keeps files
below roughly 200 lines where practical.

## Grading Tiers

1. **Deterministic** (free, reproducible): output match, AST tool-call match
   (schema-first — validates against the tool schema and never repairs invalid
   arguments), state and trajectory constraints.
2. **Execution** (objective): run tests in an isolated environment; tests are the
   oracle.
3. **LLM-as-judge** (last resort): only irreducibly subjective qualities,
   calibrated against humans (Cohen's κ, inter-annotator agreement) before use.

Verification is a tagged union (`VerificationSpec`) so illegal states are
unrepresentable; the spec-time `ExpectedToolCall` is distinct from the runtime
`ToolCall` (which carries `call_id`).

## Testing Strategy

- Unit tests cover pure functions without mocks.
- Integration tests cover edges with recorded fixtures.
- A **golden conformance suite** of hand-verified trajectories is the correctness
  oracle; a secondary differential check runs the same tasks through Inspect AI.
- Property-based tests guard invariants (canonicalization is idempotent; a
  schema-invalid argument never passes; same seed + input is deterministic).
- Every behavior change begins with a failing test.

## Initial Vertical Slice (slice 001 — landed)

The Weeks 1–2 tool-use slice delivered all eight spec deliverables:

- **Locked record spine** (`tasks/`): frozen kw-only dataclasses for
  `ExpectedToolCall`, `ToolCall`, `Turn` (tagged union), `ToolOutcome`,
  `VerificationSpec` (tagged union with `ensure_supported` guard), `Task`,
  `GradeResult`, `Trajectory`, `RunResult`; pure `to_dict`/`from_dict` codec
  with explicit `type` discriminators; JSONL loader at the edge.
- **Synthetic workspace-world** (`tools/`): three schema-validated tools
  (`search_docs`, `create_ticket`, `update_ticket`) over a `{tickets, docs}`
  state subset; pure `apply(tool, args, state) -> (state', outcome)` boundary;
  a single vendored stdlib JSON-Schema validator (`jsonschema_mini.py`) shared
  by the world boundary and the AST grader so "invalid" means the same thing
  in both.
- **AST tool-call grader** (`graders/`): schema-first pipeline (parse →
  validate-vs-schema → canonicalize → structural compare) emitting a
  7-category failure taxonomy (`malformed_call`, `schema_violation`,
  `wrong_tool`, `wrong_args`, `missing_call`, `extra_call`, `order_mismatch`)
  plus `step_limit_exceeded` from the runner; `exact_sequence` and `multiset`
  match modes; never coerces types. `grade_exact_match` survives as the
  `OutputMatchSpec` scorer.
- **OpenAI-compatible provider client** (`runners/provider.py`): builds
  `/chat/completions` requests from `ProviderConfig`, parses responses into
  canonical `Turn`/`ToolCall` records, reads API key from the env var named by
  `api_key_env`; tested against a fake injected transport — no network, no
  real keys anywhere in the suite.
- **Multi-run runner** (`runners/runner.py`): model↔tool loop, explicit state
  threading via `apply`, max-turns / max-tool-calls limits, k runs per task,
  `Trajectory` records with cost + latency + `run_index` + termination reason.
- **Golden conformance suite** (`tests/graders/conformance/cases.json`): 10
  hand-verified cases covering every taxonomy category; graded through the
  harness, asserted equal to the oracle; runs in CI.
- **Baseline report + CLI** (`reports/`): pure renderer from `RunResult`s;
  `python -m agent_eval_lab.reports.baseline <runs.jsonl>` smoke target; 4
  committed recorded runs.
- **~20-task dataset** (`examples/datasets/tool_use.jsonl`): full `Task`
  records covering tool selection, argument extraction, and multi-step tasks
  with both match modes; replaces the name-only `tool_selection.jsonl`.
