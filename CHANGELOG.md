# Changelog

All notable changes documented here. Format: [Keep a Changelog](https://keepachangelog.com/).

## v0.2.0 — 2026-06-10

Weeks 1–2 tool-use evaluation slice — a minimum, reproducible eval system for tool
use & function-calling (functional-core / imperative-shell, TDD).

### Added
- Locked immutable data spine (`tasks/`): `ExpectedToolCall`/`ToolCall`, the `Turn`
  and `ToolOutcome` tagged unions, the `OutputMatchSpec`/`ToolCallMatchSpec`
  verification subset (open union with a dispatch guard for not-yet-implemented
  variants), `Task`/`TaskInput`/`TaskMetadata`, `GradeResult`/`Trajectory`/`RunResult`,
  and a pure JSONL codec + dataset loader.
- Synthetic `workspace-world` (`tools/`): `search_docs`, `create_ticket`,
  `update_ticket` over `{tickets, docs}` state, each a JSON schema plus a pure
  `apply(tool, args, state) -> (state', outcome)`. Schema validation at the boundary
  returns `ToolFailure` (like a real API 400) and never mutates state on a violation.
- Vendored, dependency-free minimal JSON-Schema validator shared by the world
  boundary and the grader, so both agree on what "invalid" means.
- Schema-first AST tool-call grader (`graders/`) with a structured failure taxonomy
  (`malformed_call`, `schema_violation`, `wrong_tool`, `wrong_args`, `missing_call`,
  `extra_call`, `order_mismatch`) and `exact_sequence` / `multiset` match modes;
  value-preserving, idempotent argument canonicalization (never coerces types).
- OpenAI-compatible provider client (`runners/`) parameterized by `ProviderConfig`
  with an optional tool-call-dialect adapter hook, built test-first against an
  injected fake transport (no network, no API keys).
- Multi-run runner (`runners/`): model↔tool loop with explicit state threading,
  max-turns / max-tool-calls limits, **k runs per task from day one**, cost/latency
  capture, and a deterministic trajectory hash.
- ~20 tool-use tasks (`examples/datasets/tool_use.jsonl`) covering tool selection
  and argument extraction; a golden conformance suite as the grader's oracle; and
  Hypothesis property tests (canonicalization idempotence, schema-invalid-never-passes,
  determinism).
- Baseline report + CLI (`reports/`): pure report model + renderer, surfacing
  per-task `pass^k` reliability, cost/latency, and failure-category counts;
  `python -m agent_eval_lab.reports.baseline <runs.jsonl>`.

### Changed
- Migrated `GradeResult` from `{passed, score, feedback}` to the canonical
  `{grader_id, passed, score, evidence, failure_reason}`; `grade_exact_match`
  survives as the `OutputMatchSpec` scorer (its message moved into `evidence`).
- Replaced the name-only `examples/datasets/tool_selection.jsonl` with full `Task`
  records carrying `VerificationSpec`, JSON-schema tools, and provenance metadata.

### Fixed
- The `OutputMatchSpec` scorer no longer mislabels an output-text mismatch with the
  tool-call category `wrong_tool` (now `failure_reason=None`), keeping
  failure-category counts meaningful on mixed datasets.
- The AST grader now reports `order_mismatch` (not `wrong_args`) when the same tool
  is called more than once with its arguments in the wrong order.
