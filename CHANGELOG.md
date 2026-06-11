# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added — Weeks 5–6 coding agent evaluation

- Code-world (item 001): in-memory file-tree state with four agent tools
  (`read_file`, `write_file`, `list_files`, `run_tests`) following the pure
  `apply()` pattern; `run_tests` returns an `ExecutionRequest` effect-request
  fulfilled by the runner loop at the edge (ADR-0008).
- Hermetic pytest execution edge: materializes a file tree into a fresh temp
  dir, runs pinned-interpreter pytest in a from-scratch scrubbed environment
  under a hard timeout (process-group SIGKILL), parses JUnit XML into typed
  per-test records, and canonicalizes output so serialized results are
  byte-identical across runs (ADR-0009). Corrupt JUnit XML and reserved
  `.junit.xml` / casefold-colliding paths are rejected deterministically
  rather than silently mismatching the in-memory world.
- `code_repair_v1` dataset (item 003): 15 hand-authored, reviewed code-repair
  tasks (`cr-001`–`cr-015`; tiers 2/4/6/3, 60% T3/T4; 6 capabilities, 6 bug
  classes, 6 difficulty knobs) over the code-world with held-out oracle tests;
  visible/oracle disjointness and oracle breadth proven mechanically
  (ADR-0012), hardcode-style hack fixtures per weak-oracle task, review ledger
  under `cr-rubric-v1`, sha-frozen sidecars, and a 32-test anti-rote
  conformance suite running the production oracle edge in CI (no-op agent
  grades 0/15 by construction).
- Execution-based grading (item 002): `ExecutionSpec` verification variant
  carrying held-out oracle tests; oracle-wins overlay over the agent's final
  tree (ADR-0010); pure `graders/execution.py` consuming a verdict map keyed
  by `execution_hash` (ADR-0011), precomputed at `runners/oracle_edge.py`;
  dispatch + JSONL parse/serialize round-trip; 9 golden conformance cases run
  real sandboxed pytest. Reward-hacking hardening: `--noconftest`, reserved
  root-level `sitecustomize.py`/`usercustomize.py` startup hooks, oracle
  secrecy tests; the residual in-process import boundary is documented in
  ADR-0010.

### Added — Weeks 3–4 dataset and grader quality

- Live v2 validation: four conditions at k=3 (deepseek-v4-pro 1.000/1.000,
  GLM-5.1 1.000/1.000, MiniMax-M3 0.980/0.940, local Qwen3-8B 0.620/0.620 —
  pass@1/pass^3) with cluster-bootstrap-by-task CIs; committed
  failure-mode/validation report with per-tier curves, failure taxonomy ×
  tier × capability, deterministic-vs-flaky split, and a mechanical
  discriminativeness verdict (weak rung met: v2 is no longer saturated;
  hosted separation a named near-miss at n=50).
- Pre-declared two-configuration comparison (deepseek default vs frozen
  hash-pinned planning prompt, paired on all 50 tasks): primary T3+T4
  Δ pass^3 = 0.000 [0.000, 0.000] → "no detectable effect at n=50" read
  mechanically off the frozen decision rule; planning regressed one T2 task.
- Per-task `metadata.max_steps` honored by the runner (ADR-0004; CLI flag
  stays the fallback; v1 behavior unchanged) and `--system-prompt-file`
  with prompt-config artifact tags (ADR-0007; empty tag keeps v1 filenames
  byte-identical).
- Pure `report-validation` and `compare-configs` CLI subcommands —
  deterministic regeneration from captured run JSONL (byte-identical on
  re-run, seeded bootstrap), loud structured errors on malformed lines,
  task-universe mismatches, unmapped capabilities, and sub-k partial tasks
  (excluded and named, never vacuously passed).
- Model-based grader: `LlmJudgeSpec` joined the `VerificationSpec` union —
  pure prompt build / response parse / spec-tree collection in
  `graders/judge.py`, with judge calls confined to an explicit edge; verdicts
  are pre-computed and threaded into pure grading keyed by prompt hash
  (ADR-0005). Judge failures are explicit sum types carried in evidence,
  never coerced into agent failures.
- Calibration harness: blind versioned annotation packets (export / LLM-label
  / compute via `calibrate` CLI subcommands with atomic writes), pure
  `metrics/agreement.py` — binary Cohen's κ headline + quadratic-weighted κ
  secondary (ADR-0006) + seeded percentile bootstrap CI with degenerate-
  resample accounting, all pinned to hand-computed literature vectors.
- 20 committed calibration fixtures (incl. four near-miss boundary cases
  added after adversarial review) with intended labels kept outside the
  blind packet; calibration runbook documenting the §6 protocol state
  machine — human–human and judge–human calibration remain OPEN for human
  annotators; a provisional LLM–LLM run (deepseek + GLM, n=19 scored,
  1 judge error surfaced) measured binary κ 0.87 / weighted 0.94, labeled
  PROVISIONAL throughout.
- Workspace-world v2: five new schema-validated pure tools (`get_account`,
  `list_tickets`, `send_email`, plus deliberate distractors `archive_ticket`,
  `find_account`, `draft_email`); state grows to
  `{tickets, docs, accounts, emails}`.
- `workspace_tool_use_v2`: 50 reviewed, capability-discriminating tasks
  (`ws2-001`…`ws2-050`) across six capabilities and four difficulty tiers
  (66% hard: T3=22, T4=11) — long-horizon state-dependent chains, derived
  arguments (filter/compare/aggregate over returned data), distractor
  pressure, and layered `AllOf` constraint stacks; every task carries
  difficulty-knob, provenance, review, and `world_template_id` metadata.
- Task taxonomy and scoring-rubric docs plus a per-task review ledger.
- Dataset conformance suite (15+ pure checks in CI): parse, registered tools
  only, schema-valid expected calls, distractors never the expected path,
  initial-state preconditions, anti-rote state-dependency proxy (22/33 hard
  tasks pinned), tier/capability mix, and a no-op guarantee — a zero-tool
  agent grades 0/50 by construction.
- `TaskMetadata.max_steps` (per-task step budget; runner wiring lands with the
  validation item per ADR-0004) and `TaskMetadata.review`.
- Composite verification layer: `FinalStateSpec`, `TrajectorySpec`, and `AllOf`
  joined the `VerificationSpec` union, with constraint variants
  (`StateEquals`/`StateContains`; `NoToolCall`/`OnlyModifies`/`MaxToolCalls`)
  interpreted by pure graders — outcome checks are path-independent while
  trajectory constraints still police side effects.
- `Trajectory.final_state` records the post-loop world state and is threaded
  from the runner into grading; serialization round-trips it.
- `OnlyModifies` uses dot-segment-aware prefix coverage (`tickets.T-1` does not
  cover `tickets.T-10`) over a leaf-level state diff; empty mappings contribute
  no leaves, eliminating phantom-path false failures.
- `forbidden_action` and `step_limit_exceeded` failure categories now emitted
  by trajectory-policy grading; `AllOf` reports the first sub-spec failure
  category while evaluating all sub-specs.
- Golden conformance suite extended from 11 to 23 hand-verified cases
  (state success/failure, missing paths, policy breaches, path-independent
  success via two distinct valid routes, conjunction semantics).

### Added — Weeks 1–2 tool-use vertical slice

- Immutable record spine (`records/`): conversation turns, runtime tool calls,
  trajectories with usage/stop-reason/parse-failure capture, grade results with
  the structured failure taxonomy, and dict round-trip serialization.
- Locked `VerificationSpec` subset (`OutputMatchSpec | ToolCallMatchSpec`) with
  task schema, pure parser, and JSONL dataset loader.
- Synthetic `workspace-world` (`tools/`): three JSON-Schema-validated tools
  (`search_docs`, `create_ticket`, `update_ticket`) implemented as pure
  `apply(tool, args, state) -> (state', outcome)`; the world and the grader
  share one validator, so "schema-invalid" means the same thing to both.
- Schema-first AST tool-call grader (`graders/tool_call.py`) emitting
  `malformed_call`, `schema_violation`, `wrong_tool`, `wrong_args`,
  `missing_call`, `extra_call`, `order_mismatch`; canonicalization is
  value-preserving and never repairs arguments.
- OpenAI-compatible provider client with a six-provider registry
  (DeepSeek, GLM, MiniMax, Qwen, OpenRouter, local), retry, and latency capture.
- Model↔tool loop with step limits and a multi-run executor (`run_task_k`)
  producing graded `RunResult` records — multi-run from day one.
- Pure metrics: `pass@1` (trial accuracy), `pass^k` (task-level reliability,
  validated against the actual runs per task), failure counts, token totals,
  and derived cost from explicit `TokenPrice` inputs.
- Baseline report (pure build + markdown render) and the
  `run-baseline` CLI writing the report plus full graded JSONL traces.
- 20-task workspace tool-use dataset (tool selection, argument extraction,
  multi-step) replacing the legacy seed dataset.
- Golden conformance suite: 11 hand-verified trajectories as the harness
  correctness oracle, plus Hypothesis property tests (canonicalization
  idempotency; schema-invalid arguments never succeed).

### Fixed

- Run artifacts are now named by the full condition id (provider **and**
  model), so evaluating two models under the same provider no longer
  overwrites each other's traces and reports.
- Tool-call argument parsing no longer crashes when a provider returns
  arguments as an already-decoded JSON object (dialect quirk — accepted
  value-for-value); genuinely unsupported argument types are recorded as
  parse failures (graded `malformed_call`) instead of raising.
- Run results stream to the JSONL trace file per task, so completed runs
  survive a mid-dataset provider failure.
- Harness misconfiguration (registered tool without implementation, task
  referencing unknown tools, malformed provider responses) fails loudly or is
  recorded explicitly instead of being silently graded as an agent failure.
- Half-specified `--input-price-per-mtok`/`--output-price-per-mtok` flag pairs
  are rejected instead of silently skipping cost estimation.

## [0.1.0] - 2026-06-09

### Added

- Initial scaffold: pure exact-match grader with tests, seed tool-selection
  dataset, pytest + ruff CI, architecture and roadmap docs, and the eval
  pipeline design spec.
