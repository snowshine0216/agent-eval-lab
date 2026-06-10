# 001 — Weeks 1–2 Tool-Use Vertical Slice (spec)

> **Provenance:** scoped extract of
> [docs/superpowers/specs/2026-06-09-agent-eval-pipeline-design.md](../../superpowers/specs/2026-06-09-agent-eval-pipeline-design.md)
> — §16 (next step), §11 (Wk 1–2 row), §3 (architecture/provider), §4 (data
> model), §5 (tool-world), §6 (graders), §8 (conformance), §12 (testing/CI),
> §13 (current-vs-proposed delta). The design doc is the "why" record; this file
> is the **acceptance contract** for the slice. Where the two ever disagree, the
> design doc's rationale wins and this file is corrected.

## Goal

Ship a minimum, reproducible **tool-use evaluation system**: a locked immutable
data spine, a deterministic synthetic tool-world, a schema-first AST tool-call
grader with a structured failure taxonomy, an OpenAI-compatible provider client,
a multi-run runner that captures cost/latency, a golden conformance suite that is
the grader's correctness oracle, and a baseline report. Functional-core /
imperative-shell throughout; TDD red-green-refactor.

## In scope (the eight deliverables)

1. **Locked `VerificationSpec` subset + task schema** — the immutable record types
   below (§ "Locked data model"), serializable to/from JSONL, round-trip tested.
2. **Synthetic `workspace-world`** — **2–3 tools**, each a JSON Schema (fed to the
   model as `available_tools`) **and** a pure
   `apply(tool, args, state) -> (state', result)` over explicit in-memory state.
   Args are validated against the tool's JSON Schema **at the runtime boundary**;
   a violation returns a `ToolFailure` (exactly as a real API returns 400) — the
   world never silently repairs a bad argument.
3. **~20 tool-use tasks** — `Task` records covering **tool selection** and
   **argument extraction**, over the locked schema, with a mix of difficulty
   knobs (distractor tools, argument complexity). Replaces/extends the current
   name-only `examples/datasets/tool_selection.jsonl`.
4. **AST tool-call grader + failure taxonomy** — the schema-first pipeline (parse
   → validate-vs-schema → canonicalize value-preserving only → structural
   compare), emitting a structured `FailureCategory`. `exact_sequence` and
   `multiset` match modes. Never coerces types (coercion ⇒ `schema_violation`).
5. **OpenAI-compatible provider client** — one client parameterized by
   `ProviderConfig`; an optional pure `adapter` normalizes tool-call dialect
   quirks at the edge so the core only sees canonical `ToolCall`/`Turn` records.
6. **Multi-run runner with limits + cost capture** — imperative shell: model↔tool
   loop, explicit state threading, retries/limits (max turns, max tool calls),
   **N runs per task from day one**, emits `Trajectory` records carrying turns +
   usage/cost + latency + `run_index` + a termination reason.
7. **Initial golden conformance suite** — hand-verified recorded trajectories with
   known-correct grades covering malformed calls, schema violations, wrong
   tool/args, missing/extra calls, and order mismatch; graded through *our*
   harness, asserted equal to the oracle; runs in CI.
8. **Baseline report** — a pure report model + renderer turning `RunResult`s into a
   baseline summary (per-task pass and aggregate pass count over k runs, total &
   mean cost/latency, failure-category counts); file I/O at the edge.

## Out of scope (later weeks — design must stay additive)

Final-state/composite verification (`FinalStateSpec`, `TrajectorySpec`, `AllOf`),
LLM-judge + calibration, execution graders, `ExperimentSpec`/`ExperimentResult`
and bootstrap CIs, multi-turn / `ScriptedUser`, leakage-safe splits, dataset
generator, `TrajectoryExample` export, finetuning. The locked types below are
designed so each of these is a **purely additive** extension (new union variant +
new pure interpreter), never a rework of what lands here.

## Locked data model (immutable spine)

All records are `@frozen(kw_only=True)` dataclasses (or equivalent), JSONL-serializable,
behavior in pure functions not on records. Authoritative shapes: design §4.1–§4.5.

- **Tool calls (distinct spec-time vs run-time):** `ExpectedToolCall{name, arguments}`
  (no `call_id`) and `ToolCall{call_id, name, arguments}`.
- **Turns (tagged union, explicit `type` discriminator):** `MessageTurn`,
  `ToolCallTurn{tool_calls: tuple[ToolCall,…], content?}`, `ToolResultTurn{call_id, outcome}`
  where `ToolOutcome = ToolSuccess{result} | ToolFailure{error}`. `Turn` is their union.
- **Verification (tagged union; only the tool-use subset is implemented now):**
  `OutputMatchSpec{expected_output, normalizer?}` and
  `ToolCallMatchSpec{expected_tool_calls: tuple[ExpectedToolCall,…], match: "exact_sequence"|"multiset"}`.
  `VerificationSpec` is an **open** union + dispatch designed for additive variants;
  unimplemented variants (final-state/trajectory/execution/judge/all-of) are **not**
  built this slice and the dispatcher must reject them with a clear, typed error
  rather than silently passing.
- **Task:** `Task{id, capability, input, verification, metadata, initial_state?}`
  where `input = TaskInput{messages, available_tools}` (available_tools = JSON
  schemas) and `metadata = TaskMetadata{split, version, provenance, world_template_id, difficulty_knob}`.
  Single-turn only this slice — no `scripted_user`.
- **Grading:** `FailureCategory` literal (tool-call members emitted this slice:
  `malformed_call, schema_violation, wrong_tool, wrong_args, missing_call,
  extra_call, order_mismatch`; `step_limit_exceeded` may be emitted by the runner's
  limit path). `GradeResult{grader_id, passed, score, evidence: Mapping, failure_reason: FailureCategory|None}`.
- **Runs:** `Trajectory` (turns + usage/cost + latency + `run_index` + termination
  reason) and `RunResult{task_id, condition_id, run_index, trajectory, grade}`.

### `GradeResult` migration (reconcile with current checkout)

Current checkout has `GradeResult{passed, score, feedback}` in
[src/agent_eval_lab/graders/exact_match.py](../../../src/agent_eval_lab/graders/exact_match.py).
This slice migrates it to the canonical `GradeResult{grader_id, passed, score,
evidence, failure_reason}`. The existing human-readable `feedback` string is
carried inside `evidence` (e.g. `evidence["message"]`). `grade_exact_match`
survives as the **`OutputMatchSpec` scorer** and is updated to return the new
shape; its test is updated accordingly. This is the design's intended evolution
(§13: "extends them, does not contradict").

## Acceptance criteria (concrete, checkable)

- **A1.** All locked record types exist as frozen, kw-only, immutable dataclasses
  and **round-trip through JSONL** (`to_dict`/`from_dict` or equiv.) losslessly —
  including the tagged-union `type` discriminators for `Turn`, `ToolOutcome`, and
  `VerificationSpec`. Unit-tested, no mocks.
- **A2.** `workspace-world` exposes 2–3 tools, each with a JSON Schema and a pure
  `apply`. A schema-valid call mutates a *copy* of state and returns a
  `ToolSuccess`; a schema-**invalid** call returns a `ToolFailure` and **does not**
  mutate state. Pure (no I/O, argument not mutated), tested directly.
- **A3.** The AST grader implements the schema-first pipeline and emits the correct
  `FailureCategory` for: parse failure (`malformed_call`), schema violation incl.
  type-coercion attempts (`schema_violation`, never a silent pass), wrong tool
  (`wrong_tool`), wrong args (`wrong_args`), missing call (`missing_call`), extra
  call (`extra_call`), order mismatch in `exact_sequence` (`order_mismatch`).
  `multiset` mode ignores order but preserves duplicate count.
- **A4.** Canonicalization is **strictly value-preserving** and **idempotent**
  (property-based test, Hypothesis). A schema-invalid argument **never** grades as
  pass (property-based test).
- **A5.** The provider client builds OpenAI-compatible `/chat/completions` requests
  from `ProviderConfig` and parses responses (incl. tool calls) into canonical
  `Turn`/`ToolCall` records, with the optional `adapter` hook applied at the edge.
  **Tested against a fake/recorded transport — no network, no API keys.** API key
  is read from the env var *named* by `api_key_env` (never hard-coded).
- **A6.** The runner runs the model↔tool loop, threads world state explicitly,
  enforces max-turns / max-tool-calls limits (limit hit ⇒ recorded termination
  reason, `step_limit_exceeded` where graded), runs **k ≥ 2 runs per task**, and
  emits `Trajectory` records with cost + latency + `run_index`. Driven by a
  **deterministic fake model** in tests; determinism guard: same seed + input ⇒
  identical trajectory hash (property/unit test).
- **A7.** A golden conformance suite of hand-verified trajectories grades through
  the harness and **matches the oracle** for every taxonomy category in A3. Runs
  under `uv run pytest` in CI.
- **A8.** The baseline report renders deterministically from `RunResult`s (per-task
  pass + aggregate pass-over-k + total/mean cost/latency + failure-category
  counts). Report **model + rendering are pure**; only the final write is at an
  edge. A committed example baseline report is produced from recorded/fake
  trajectories.
- **A9.** `uv run pytest`, `uv run ruff check .`, and `uv run ruff format --check .`
  all pass. New dev deps (e.g. `hypothesis`) added to `[dependency-groups].dev`;
  CI (`.github/workflows/ci.yml`) stays green without secrets/network.
- **A10.** Docs updated to match what shipped: `docs/ARCHITECTURE.md` (module map
  already anticipates this; reconcile any drift) and the dataset note for the new
  task format. The current-vs-proposed delta (design §13) is moved toward "done"
  for the landed pieces.

## Constraints (hard)

- **Functional core / imperative shell** (AGENTS.md, CLAUDE.md): `tasks/`,
  `tools/`, `graders/`, `metrics/`, `reports/` *models* are pure — no network,
  process exec, file access, logging, or argument mutation. Effects only in
  `runners/` and the I/O edges of `reports/`/dataset loaders.
- **Immutability:** `const`-by-default mentality; build new records via spread,
  never mutate inputs. Records carry data, not behavior.
- **TDD:** every behavior change starts with a failing test. Pure core → unit
  tests, **no mocks**. Edges → integration tests with **recorded fixtures**.
- **Schema-first, never repair:** the grader must not be more lenient than the
  runtime; type coercion is a `schema_violation`, not a silent pass (design §6/§7).
- **No live model calls / no secrets** anywhere in the test suite or CI.
- **Style:** files < ~200 lines, functions < ~20 lines where practical; ruff
  clean; module layout per design §3 / `docs/ARCHITECTURE.md`.

## Module layout (target)

```
src/agent_eval_lab/
  tasks/     Task + VerificationSpec + tool-call/turn types + validation (PURE) · JSONL loader (edge)
  tools/     workspace-world: JSON schemas + pure apply() over explicit state (PURE)
  runners/   provider client (ProviderConfig), model↔tool loop, limits, multi-run → Trajectory (EDGE)
  graders/   OutputMatch (exact_match survives) + schema-first AST tool-call grader (PURE)
  metrics/   minimal aggregation for the baseline report (pass-over-k, cost/latency) (PURE)
  reports/   pure report model + renderer · file write (edge)
```

## Left to the plan (writing-plans decides)

- The exact 2–3 tools and the `{tickets, emails, docs, accounts}` state subset.
- Serialization mechanism (hand-rolled `to_dict`/`from_dict` vs a small typed
  codec) — must stay dependency-light and pure.
- JSON Schema validation approach (vendored minimal validator vs a dev/runtime
  dep) consistent with "dependency-light"; whichever is chosen, it is applied
  identically in the world boundary and the grader so they agree on "invalid".
- Fake-transport / cassette mechanism for client+runner tests.
- Phase ordering for TDD (suggested: types+round-trip → world+apply → AST grader
  +conformance → client+adapter → runner+multi-run → metrics+report → docs).
- Whether a thin CLI entry point is included for the baseline report (a `/verify`
  smoke target is valuable; keep it minimal if added).
