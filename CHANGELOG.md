# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## v0.2.1 — 2026-06-15

### Changed — fc-v4 classifier + pass^k censoring (harness-rounds-f-ablation step 1)

- **Classifier `fc-v3 → fc-v4`** (`reports/classify.py`): `first_execution_evidence` now accepts a
  `node_execution` grader leg so failing node-F runs classify as `agent_failure / oracle_red` instead
  of the catch-all `other_miss`; the budget override fires on the loop's real stop reasons
  (`max_steps` + `safety_cap` + `max_rounds`); the row-1 `passed` short-circuit is guarded with
  `and not cap_bound` so a graded-passed-but-budget-capped run classifies as the new
  `agent_failure / budget_exhausted` subcategory (closed vocabulary 19 → 20). ADR-0013 amended.
- **`pass^k` honors its declared `censoring_policy="failure"`** (`metrics/reliability.py`):
  `pass_pow_k` / `task_reliability` (and the bootstrap-CI + Fisher-F paths that route through them)
  count a run as a pass iff `grade.passed AND NOT (safety_cap_bound OR max_rounds_bound)`;
  `max_rounds_bound` is read defensively (the producing field lands in a later step). Verified to move
  **zero** historical pass^k numbers (no committed record is `passed AND capped`); only taxonomy
  outputs move (e.g. `other_miss → oracle_red`), as intended.

## v0.2.0 — 2026-06-15

### Added — D-set resume: interrupted runs continue without re-running banked tasks

- **`_completed_dset_task_ids` + `run-dset` resume path** (`cli.py`): a transient
  failure (network blip, system restart) mid-corpus no longer discards banked
  tasks. On relaunch, completed task ids are reconstructed from the existing JSONL
  + void sidecar; remaining tasks are identified and appended; the void sidecar is
  merged so prior voids survive the second run. Early-exit guard prevents the
  re-run from calling `run_dset` when every task is already finished. Covered by
  `tests/test_dset_resume.py` (5 unit tests over the pure helper).

### Added — F-domain candidate-edit run (the model actually fixes the repo)

- **`runners/f_candidate.py` + `run-f` CLI command**: the live F-domain eval the
  owner asked for. The candidate model edits the pinned `web-dossier` checkout
  through pure code-world file-edit tools and the held-out node oracle grades the
  model's **produced** tree — preserving the model's real trajectory (tokens /
  rounds / wall-time / cost), unlike 009's synthetic zero-usage `_grade_tree`.
  Each F task runs `k` **independent** model attempts (D-set parity); env-free, so
  every attempt is valid — no validity mask, no VOID. `run-f` is standalone
  per-arm (run-dset parity) so F runs without re-triggering the live D-set, and
  writes `runs-m1-<slug>-F.jsonl` (+ an empty `.void.json`) for `report-m1`.
- **`str_replace` tool** (`tools/code_world.py`): a targeted single-unique-
  occurrence edit primitive so large files (e.g. the 37 KB `wdio.conf.ts`) are
  edited in place rather than rewritten whole (measures fixing, not transcription;
  avoids `max_tokens` truncation). Additive to the code-world registry — used by
  the F arm, not by `code_repair`.
- **F3 candidate tree** seeds the full `failure-analysis` causal layer at the
  pinned base SHA so the held-out guard tests (`correlate`/`signal`/`compose`/
  `index`) run; the golden grading test is never seeded (D19); `m2021` HEAD is
  never read (D32). See ADR-0015.

### Fixed — `run-f` error handling: uncaught subprocess failure + missing void sidecar on abort

- **`subprocess.CalledProcessError` / `FileNotFoundError` now caught** (`cli.py`,
  `_run_f_command`): a missing `web-dossier` repo or git binary caused an
  unhandled traceback instead of a clean exit-1 message; the void sidecar and
  partial JSONL were abandoned. Now caught with an actionable diagnostic.
- **Void sidecar always written on abort** (`cli.py`, `_run_f_command`): the
  `.void.json` write was after the `try/except` block and skipped on
  `httpx.TransportError`, silently dropping void task ids. Moved into `finally`
  so `report-m1` always finds a sidecar regardless of abort reason.

### Fixed — F-domain per-arm `condition_id` attribution (execute-phase pre-req)

- **`run_f` / `run_m1` F branch** (`runners/f_run.py`, `experiments/m1_run.py`):
  the F-domain runner hard-coded every emitted `RunResult.condition_id` to the
  stub `"(f-local)"`, so a multi-arm M1 report could not attribute F outcomes to
  the model under test. `run_f` now takes a required `condition_id` and threads it
  through `_grade_tree` into every `RunResult`; `run_m1` passes the real per-arm
  `cond` (D-set parity). This is the `EXECUTE-DEFERRED.md` §2 F-domain pre-req —
  F is env-free, so with this wired the candidate F arms are runnable. Covered by
  a new `test_run_f_threads_condition_id_into_runresults`.
- Doc-sync: the superseded foundation `HANDOFF.md` now banners forward to the
  `agentic-v1-domains-runs` phase and corrects its stale "designed, not built"
  rows for F (009) and B/M2 (010), both built + merged.

### Fixed — D-set bash edge: playwright daemon leak + sub-task liveness signal

- **Daemon leak in `make_bash_executor`'s `close()`** (`runners/bash_edge.py`):
  `close()` only `rmtree`'d the workdir, never stopping the persistent, detached
  `cliDaemon.js` (and its Chrome) that each `playwright-cli -s=<name> open`
  spawns — ~1.6 daemons/min leaked over a live D-set run. The model picks
  arbitrary session names, so name-targeting is impossible; instead the executor
  now scopes the daemon registry per-workdir via `PWTEST_DAEMON_SESSION_DIR` and
  `close()` runs the tool's own `close-all` over that scoped registry (graceful
  stop, closes Chrome too), reaping exactly this executor's daemons — never the
  machine's other playwright-cli sessions. Time-bounded and best-effort.
- **Sub-task liveness heartbeat** (`runners/bash_edge.py`, `runners/dset_run.py`,
  `cli.py`): the per-task runs JSONL was the run's only progress signal and is
  too coarse — one hard live task outlives any sane stall threshold, so a
  watchdog watching only the JSONL false-kills healthy in-task work. The
  executor (the I/O edge) now emits a per-command heartbeat; `run-dset` writes it
  to `runs-dset-<slug>.heartbeat` (content = live task id, mtime = the watched
  signal) so a stall watchdog can use a tight threshold without spelunking
  playwright internals.

### Added — B-domain adapter + M2 skill-effect machinery (item 010)

- Third M1 macro-composite domain (B) — long-horizon MicroStrategy Library GUI
  automation graded by an **evaluator-credentialed readback oracle** against an
  evaluator-only golden (§4.3/§18.7). The candidate never sees the golden
  (D19/D33); the report engine already renders B generically.
  - **Per-run isolation (D20)** (`runners/b_isolation.py`): a unique save name
    `<model>-<condition>-<run_id>` derived from `Trajectory.run_uid`, a
    preflight-absence assert, capture-the-created-object-id on save, and
    reset/cleanup after grading — the grader keys on the captured object id,
    never a name search.
  - **Readback oracle** (`datasets/b1_oracle.py`, new `ReadbackSpec`): a pure,
    total, golden-discriminating grader — (1) the captured object exists,
    (2) definition matches (cube `Query_CharacteristicValue_Mandatory`,
    Rows ⊇ {Years Hierarchy, Region}, Cols ⊇ {Cost}, prompt = South),
    (3) executed grid == golden grid. golden ⇒ PASS; wrong cube / missing row /
    missing Cost col / wrong prompt ⇒ FAIL (≥1 negative fixture per mode, D24).
  - **M2 (D25/D37)** (`datasets/b_tasks.build_b_tasks`): B-noskill vs B-skill —
    the same B-1 task and the IDENTICAL harness instrumentation; the only
    difference is a stripped knowledge-only `strategy-test` `SKILL.md` fork
    injected as the B-skill system prompt (`datasets/skill_loader.py`, §18.9/D27).
    The estimand is the bundled stripped-skill effect, never knowledge-only.
- All MSTR/`playwright-cli` I/O goes through an injectable `MstrReadbackClient`
  Protocol (`runners/mstr_client.py`) — stubbed by a deterministic fake in every
  test (no live infra in the suite). `runners/b_run` + `experiments/m1_run` gain
  a B branch (absent ⇒ skipped, never a crash); `cli._load_m1_domain_tasks`
  returns D, F **and** B when the gitignored evaluator store is present.
- Config (`experiments/evaluator_config.py`): typed `CandidateConfig` for the
  least-priv candidate account + `project_id`/`goldens` on `OracleBSetConfig`.
- Integrity: creds / MSTR host / golden object id / golden grid live ONLY in
  gitignored `evaluator.toml` + `evaluator-only/`; the B-1 candidate prompt stays
  at fair problem level (no golden id, no grid value); golden/mutant fixtures live
  ONLY in the gitignored evaluator store, guarded by `requires_store` skipif so CI
  skips them. **B-2..B-10 + their goldens are not provided → M2 over B-1 is a
  1-task contingency, never a cluster-bootstrap CI (D26).**
- **Live MSTR runs are deferred** — this lands the deterministic machinery only;
  the live readback + the M2 arm execution are in the owner's `EXECUTE-DEFERRED`
  runbook.

### Added — F-domain repo adapter: F1/F2 env-free oracles + run-m1 wiring (item 009)

- Second M1 macro-composite domain (F) over the `web-dossier` wdio toolchain,
  reusing the F3 `NodeExecutionSpec`/`node_edge` pattern: held-out node `--test`
  oracles overlaid on the candidate's produced file tree, graded behaviorally
  (the changed unit is extracted and executed with injected fakes — not
  token-grepped), so structural-only solutions are rejected (D24).
  - **F1** (`datasets/f1_oracle.py`): TC99396_10 must drop the flaky image
    comparison and assert deterministically on the named-snapshot notification
    reaching a terminal state. Golden-discriminating: golden ⇒ PASS, pre-fix
    base ⇒ FAIL, keeps-image-compare / error-path-gutted mutants ⇒ FAIL.
  - **F2** (`datasets/f2_oracle.py`): the wdio failure-analysis fixture must
    capture the engine result and emit a terminal diagnose trace of the failed
    (non-2XX) requests + the engine signal/confidence. Golden-discriminating:
    surfaces-2xx / omits-signal-line mutants ⇒ FAIL.
- `datasets/f_tasks.build_f_tasks` attaches the F1/F2/F3 oracles to F-domain
  tasks; `runners/f_run` + `experiments/m1_run` gain an F branch (candidate
  attempts the repo task against the frozen pre-fix base → produces a file tree
  → node oracle grades); `cli._load_m1_domain_tasks` now returns D **and** F.
- Integrity: candidate base pinned to the frozen pre-fix SHA (never the open
  PR's moving base, D32); golden source/answers + mutant fixtures live ONLY in
  gitignored `evaluator-only/` (D19/D33); candidate task prompts withhold
  localization (§4.1) — no golden-new symbol names or solution mechanics.

### Added — agentic_v1 runner hardening + provider ladder (item 008)

- Bounded tool-result context fed back to the provider: new pure
  `runners/history.trim_tool_result_history(turns, *, char_budget)` (newest-first
  greedy keep; older `ToolResultTurn` contents elided once over budget; the
  newest tool result is always kept; non-tool turns untouched; idempotent),
  wired into `loop.run_single`. Stops a context blow-up from 400-ing the
  provider mid-run. Grading is unaffected — the grader reads only the final
  assistant message + the evaluator-frozen snapshot, never the browse dumps.
- Per-run provider HTTP error is recorded, not fatal: an `httpx.HTTPStatusError`
  inside `run_single` becomes a `ParseFailure(error=PROVIDER_ERROR)` with
  `stop_reason="parse_failure"` (`raw` carries the response body only — never an
  auth header), mapped by the classifier to `harness_failure/provider_response`
  (a valid failed trial, surfaced in the taxonomy). A `TransportError` (provider
  unreachable) still propagates to the CLI's exit-1 "is the server running?" path.
- Incremental run-JSONL: `dset_run.run_dset` is now a generator yielding one
  `ReplacementOutcome` per task; the CLI flushes per task and writes a
  `<runs>.void.json` sidecar, so one bad task can no longer lose a whole
  model's run. `experiments/m1_run.run_m1` collects via `tuple(run_dset(...))`.
- Providers: default `local` model id corrected to `Qwen/Qwen3-8B` (the id the
  local ollama endpoint actually serves); added the `siliconflow` provider for
  the Qwen ladder (`Qwen/Qwen3.5-397B-A17B` default; the 35B rung via `--model`).

### Added — Weeks 5–6 coding agent evaluation

- Explicit completion budget as an eval parameter (item 004 fix round): the
  OpenAI-compatible client now requires `max_tokens` and the CLI exposes
  `--max-tokens` (default 4096) threaded through `run-baseline` →
  `run_task_k` → `run_single` → `chat_completion`, recorded on every
  trajectory (`max_tokens`, round-tripped by the serializer; absent on
  pre-fix artifacts). Closes the harness defect where provider defaults
  applied silently — the local MLX server's 512-token default truncated
  Qwen3-8B (a thinking model) inside its reasoning channel on 30/45 runs,
  misread as agent failures. Rerun under the explicit budget: local
  condition pass@1 0.133 → 1.000.
- Failure classifier fc-v2 (ADR-0013): new `token_budget_exhausted`
  subcategory (agent_failure) for parse_failure runs with
  `completion_tokens >= trajectory.max_tokens` (closed vocabulary now 16);
  None-guard classifying `stop_reason=parse_failure` without a recorded
  `parse_failure` as `harness_failure/sandbox_fault` (fc-v1 raised on this
  path); old artifacts without `max_tokens` classify exactly as before.
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
