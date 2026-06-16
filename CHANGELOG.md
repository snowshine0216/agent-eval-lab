# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Fixed

- **`python -m agent_eval_lab` now works.** Added `src/agent_eval_lab/__main__.py`, so the
  documented module invocation (used by every CLI recipe across the docs) runs instead of failing
  with `No module named agent_eval_lab.__main__`.

### Added

- **Claude Code F-baseline (`run-f-claude-baseline`).** Runs vanilla Claude Code (`claude -p`,
  Sonnet 4.6, skills off) as the agent on the F1/F2/F3 repair tasks under two tool surfaces —
  `edit-only` (Read/Edit/Write/Glob/Grep) and `natural` (+Bash) — graded by the existing held-out
  Node oracle, producing a **Claude Code baseline distinct from the v2 model ablation**. New
  `runners/claude_cli_candidate.py` materializes the seeded web-dossier tree to a temp workdir under
  a **sanitized, clean `HOME`** (owner config/skills/effort/plugin env stripped so the run is
  genuinely vanilla; auth preserved), drives `claude -p`, reads the produced tree back, and wraps it
  in a synthetic `Trajectory` that plugs unchanged into `run_f_candidate`'s strict-VOID k-loop and
  the Node oracle. Subprocess failure / timeout / unparseable output / unreadable produced-tree →
  env-invalid (`PROVIDER_ERROR`), masked out of pass^k. `summarize_baseline` rolls outcomes into
  per-(surface, base) rows (valid/invalid/VOID/pass^k/pass@1) with per-attempt JSONL for drill-down.
  Billing is the session OAuth/subscription (quota, not per-token \$); `total_cost_usd` recorded as
  an API-equivalent efficiency metric. Bounded by a 300 s wall timeout + `--max-budget-usd` (no
  `--max-turns` in CLI 2.1.177). Output dir `reports/agentic-v1/f-claude-baseline/`. `--smoke` runs
  1×F1×edit-only then stops; `--dry-run` previews the plan with no subprocess. Fail-fasts when the
  resolved Node can't run the oracle (needs Node ≥20) or the web-dossier repo is missing.

## v0.4.0 — 2026-06-16

### Added

- **Config-driven F-ablation roster.** Which models the F-set ablation compares moved out of a
  hard-coded `_CONDITIONS` constant into a committed **`f-ablation-roster.toml`** (`experiment_id`
  + an ordered `[[model]]` array of `condition_id`/`label`). Add/remove a model is now a config
  edit, no code change. New `experiments/f_ablation_roster.py` (`load_f_ablation_roster`) parses +
  validates each `condition_id` as `provider:model` against the `PROVIDERS` registry (a typo'd
  provider is rejected before any paid call). `build_f_ablation_spec` is now **pure** over
  `(conditions, experiment_id)`. `run-f-ablation` gains `--roster` (default the committed file) and
  `--arms` (run a subset of the 2×2 arms, applied to the full seeded order so survivors keep their
  position — e.g. `--arms feedback both`). The realized-order sidecar now records `experiment_id`
  + `spec_hash`, so a run is reconstructable from artifacts. ADR-0019; CONTEXT.md "F-ablation
  roster". The **F-ablation-v2** roster = `deepseek-v4-pro` / `MiniMax-M3` / `Qwen/Qwen3.6-35B-A3B`
  (GLM dropped) → 3 models × 3 bases × 4 arms × k=5 = 180 attempts.
- **Fail-fast Node-capability guard on the paid F commands.** `run-f-ablation` and `run-f` now call
  `node_supports_junit()` and **refuse before any provider call** when the resolvable node can't run
  the held-out oracle (Node < 20 lacks `--test-reporter=junit`). This complements the v0.3.1
  grader-level env-invalid routing: refuse-before-spend (here) + VOID-if-slipped-through (v0.3.1).
  Prevents a recurrence of the node-v16 incident that silently graded 180 attempts FAIL.

## v0.3.1 — 2026-06-16

### Fixed

- **An incapable node / oracle-execution error in the F3 held-out `node --test` oracle no
  longer silently scores as a model FAIL.** On node < 20 the `--test-reporter=junit` flag is
  rejected (`bad option`, exit 9) and the run is classified `status="error"`; the prior pipeline
  graded that as an ordinary 0-score FAIL, which silently scored 180 attempts 0/180 in the
  f-ablation-v2 run (`reports/agentic-v1/f-ablation-v2/INCIDENT-node-v16.md`). Such a run now
  routes to **env-invalid** (masked from `pass^k`, VOID under D34) — loudly excluded rather than
  counted as a model failure. This is a defense-in-depth backstop independent of the F CLI
  fail-fast guards.

### Changed

- **`is_env_invalid_run` (records/grade.py) now recognizes two env-invalid sources**:
  provider-side (a `chat_completion` HTTP rejection / empty `choices` on the trajectory, as
  before) **and** oracle-side — a grader stamps `env_invalid` on its own evidence when the
  grading harness itself could not run. The classifier recurses `AllOf` `sub_results` to find the
  marker (real F verifications always wrap their `NodeExecutionSpec`(s) in an `AllOf`, so the
  marker is nested). New pure predicate `is_incapable_node_result` (graders/node_execution.py):
  `status="error"` + `exit_code == 9` + zero tests. A genuine model failure (import/load crash,
  exit 1) and a `tree_collision` stay real FAILs — never masked. No D/B-set behavior changes
  (only the node grader emits the marker). Documented in ADR-0018; ADR-0015's "no VOID" refined.

## v0.3.0 — 2026-06-16

### Added — M1 report enhancement: overview rollup + deterministic per-domain subreports

- **`M1-final-report.md` becomes a thin M1 overview** (`reports/m1.py`): a new **Efficiency & cost**
  rollup per (condition, domain) — rounds median [min–max] with right-censoring annotation for
  budget-capped runs, prompt/completion/total tokens, `cost_usd`, total tool calls, safety-cap and
  max-rounds hits, dominant stop reason — plus a deterministic per-domain headline ("best pass^k …;
  cheapest on cost-frontier …") and a **Subreports** block linking each generated subreport and the
  hand-authored companions. The "Failure taxonomy" heading is renamed to **"Failure classification
  (fc-v4) per condition"** (aligns the M1 report with the glossary and `final.py`).
- **New auto-generated per-domain subreport `M1-<domain>-report.md`** (`reports/m1_detail.py`, pure
  build + render): per-task quick-reference, cross-model pass matrix (per-trial ✅❌ + dominant
  stop), per-task detail blocks (rounds/tokens/cost/tool-calls/censoring, grader-aware failure gap,
  edit signals), task-defect candidates with shared-failing-oracle-unit intersection, per-condition
  efficiency, and fc-v4 classification per task×condition. Fully derived from the run JSONL,
  deterministic (byte-identical for fixed input), regenerated on every `report-m1`.
- **Grader-aware evidence adapter** (`reports/evidence_summary.py`): `evidence_gap(grade)` maps one
  `GradeResult` to a render-ready `EvidenceGap` (F `node_execution` per-oracle-test list +
  `displaced_paths`; D `fact_key` missing/forbidden facts; administrative, degraded `no_answer`, and
  unknown-grader branches — grade-only, never raises).
- **Trajectory-derived edit signals** (`reports/edit_paths.py`): `edit_paths(trajectory,
  target_paths=…)` reports edited paths and the out-of-scope subset (descriptive, never a verdict),
  kept deliberately separate from the grade-side `displaced_paths`.
- **Shared `reports/defects.py`**: the unanimous-fail task-defect predicate is extracted from
  `final.py` into one pure module (DRY; `final.py` imports it back — behavior-neutral, guarded by its
  existing tests).
- **CLI** (`report-m1`): `--subreports/--no-subreports` (default on) + `--subreport-dir`; writes one
  `M1-<domain>-report.md` per domain beside `--out`, so the overview's links and the files never drift.
- Administrative trials (`marked_failed_not_executed`) are honored across every section — excluded
  from pass^k, task-defect candidacy, the fc-v4 classification table, and efficiency aggregation in
  **both** the per-domain subreport and the overview rollup (one shared `is_administrative` predicate,
  so the two never disagree on a metric); rendered as "not executed (owner decision)", never as a real
  0-round/0-token failure.

## v0.2.6 — 2026-06-15

### Added — run-f-ablation driver + frozen f_ablation_spec (harness-rounds-f-ablation step 6, code only)

- **Seeded block-randomized run order** (`experiments/ablation_order.py`): pure `ablation_run_order(seed,
  models, base_tasks, k)` interleaves the four arms within each `(model, base-task, repetition)` block
  (so provider drift/time can't masquerade as a P/V effect), covering each `(model × 12 task-arm × k)`
  unit exactly once (240 at k=5). Deterministic (seeded RNG, no wall-clock).
- **Frozen `experiments/f_ablation_spec.py`**: a separate ExperimentSpec (4-model roster) + an
  `AblationPolicy` (40-round F policy, 12 arms, seed) frozen by its own sha256 over `canonical_json` —
  distinct from production `m1_spec` (which keeps F=20); the committed M1 frozen spec is untouched
  (`verify_spec_hash` still passes). The ablation family is descriptive (`correction="none"`, no Holm —
  §D.2; `MultiplicityFamily.correction` widened to `Literal["holm","none"]`).
- **`run-f-ablation` CLI driver**: executes attempts in the frozen order across (model × task-arm × rep)
  — arm encoded in `task_id` — using the 12 task-arms (003), enriched trees (004), and the Factor V
  sandbox routing (005); writes **one artifact per condition** (`runs-ablation-{slug}-F.jsonl`, all 12
  arms inside) + a realized-order sidecar (atomic write). Crash-safe: validates task_id coverage upfront,
  streams per-attempt, catches transport/git errors, and preserves partial results + the sidecar on
  abort. A `--dry-run` writes only the realized order with zero provider calls.
- **No paid execution**: the driver calls a provider only on an explicit user invocation; all tests
  inject a fake run_fn. The pilot (≈24) + full 240-attempt run and the descriptive report stay deferred
  (the user triggers the run via this driver).

## v0.2.5 — 2026-06-15

### Added — Factor V confined-execution sandbox (harness-rounds-f-ablation step 5)

- **Confined `node --test` execution** (`runners/sandboxed_node_edge.py`): a new edge runs the model's
  own authored tests (`tests/authored/`) under a macOS `sandbox-exec` seatbelt profile that is
  **deny-default with an explicit read-allowlist** (candidate temp tree + node install dir + enumerated
  system paths only), `(deny network*)`, and write-only-in-tree — so model JS cannot read the held-out
  oracle (`evaluator-only/`) and exfiltrate it (the in-trajectory stdout-leak channel). The read
  allowlist (not a broad allow) is the boundary; `file-read-metadata` is scoped (no golden size/mtime
  oracle); the node install dir is asserted disjoint from `evaluator-only/`. The trusted oracle path
  (`runners/node_edge.py`) and the frozen `truncate_output` contract are untouched. macOS-only by
  design (Darwin + sandbox-exec probe); CI injects a fake executor.
- **`make_authored_test_executor`** runs the fixed `node --test tests/authored/` (model-supplied
  commands rejected; reserved-path provenance + sandbox security boundary), wired into `make_f_run_fn`
  so V arms route to it on macOS (off-macOS raises; `bare`/`prompt` keep `executor=None`).
- **Versioned V feedback record** (`records/node_feedback.py`): distinct `NodeFeedbackResult` +
  **tail-aware** rendering (node failure summary prints at the end), leaving the oracle's head-truncated
  `ExecutionResult` byte-stable. V-specific node-accurate `run_tests` ToolDef (`CODE_WORLD_TOOLS_V`);
  the shared pytest-worded ToolDef is unchanged.
- A macOS integration test asserts the sandbox **blocks** an `evaluator-only/` read + a network call and
  still runs a benign in-tree authored test. ADR-0016.

## v0.2.4 — 2026-06-15

### Added — F candidate-tree enrichment + overlay-disjointness (harness-rounds-f-ablation step 4)

- **Curated `context_paths` on the 12 F ablation arms** (`datasets/f_tasks.py`): each base seeds a
  curated context set — materialized **byte-identically across all four arms** from the pinned base
  SHA (`5b0c13a6`; m2021 never read) — so Factor P's "read the siblings / read the source" directives
  are non-vacuous. F1: `Alert.js`/`SearchBox.js`/`Panel.js` (the `waitFor*({timeout,timeoutMsg})`
  convention); F2: `failure-analysis/index.js` (the `{signal, confidence}` return shape readable from
  source); F3: none (its causal layer is already broad). The held-out golden tests (D19) and any
  visible test asserting the discriminating behavior are excluded (§11.6). Production `build_f_tasks`
  carries no `context_paths` — its trees stay minimal.
- **`build_candidate_tree` seeds `context_paths`** (`runners/f_candidate.py`) from the pinned SHA on
  top of the existing target-path / F3-causal-layer logic.
- **Overlay-disjointness invariant** (`runners/f_candidate.py`, `tests/runners/test_f_overlay_disjoint.py`):
  new pure predicate `seeded_held_out_disjoint` (reuses `tools/code_world.prefix_collision`, not
  reimplemented) + a §10.4 unit test asserting, for every F task's `NodeExecutionSpec(s)`, that
  seeded (candidate-visible) paths are disjoint from held-out oracle paths — so enrichment can never
  silently turn an arm's runs into `tree_collision`.

## v0.2.3 — 2026-06-15

### Added — F harness-factor ablation: arm-as-task + Factor P (harness-rounds-f-ablation step 3)

- **12 F task-arms** (`datasets/f_tasks.py`): new `build_f_task_arms` fans each of the 3 base F
  tasks into 4 arms (`bare`/`prompt`/`feedback`/`both`) as **distinct `task_id`s** (the M2
  arm-as-task pattern), so the ablation rides the data model the codebase already has — **no**
  `arm_id`, `ArmDef`, `tool_set_hash`, `ConditionDef`/`ExperimentSpec`, or report-join change. The
  four arms of a base share one held-out `VerificationSpec` (same object) and byte-identical
  tree-driving `initial_state`, differing only by `factor_p`/`factor_v` flags and `available_tools`.
  Each arm carries the 40-round ablation `metadata.max_rounds` (resolvable via `resolve_max_rounds`).
- **Factor P** (`runners/f_candidate.py`): a discrete, attributable `_FACTOR_P_BLOCK` (context-
  gathering nudges; "visible tests" vocabulary) appended to `_EDIT_SYSTEM` inside `make_edit_task`,
  gated by `initial_state["factor_p"]` — applied to `prompt`/`both` arms only.
- **Factor V tool surface** (deferred executor): `feedback`/`both` arms declare the `run_tests`
  tool; the sandboxed executor is item 005, so `make_f_run_fn` raises `NotImplementedError` if a V
  arm is driven live — `bare`/`prompt` stay fully runnable.

### Changed

- **Task-scoped `run_uid`** (`runners/f_candidate.py`, `records/trajectory.py`): F `run_uid` is now
  `{condition_id}__{task_id}__{run_index:04d}` (was the `__f__` literal), so 12 task-arms sharing a
  condition's run space cannot collide.

### Fixed

- **F3 candidate-tree dispatch** (`runners/f_candidate.py`): `build_candidate_tree` now matches the
  armed F3 ids (`f-f3-*`), not just the bare `f-f3`, so armed F3 arms get the failure-analysis causal
  layer instead of silently falling through to the prefix tree (would have produced corrupt 0-scores).
- **`ruff check` clean** over the whole repo: wrapped two pre-existing long-line lint errors
  (`tests/runners/test_dset_run.py`, `tests/runners/test_loop.py`) so CI's `ruff check .` passes.

## v0.2.2 — 2026-06-15

### Added — per-domain `max_rounds` turn-bound + recorded policy fields (harness-rounds-f-ablation step 2)

- **`max_rounds` turn-bound** (`runners/loop.py`): `run_single` gains `max_rounds: int | None`
  (default `None` ⇒ unchanged), checked at the **end** of each iteration beside `safety_cap` so the
  turn's work is kept; a `max_rounds` stop means the model was still editing at the cap. New
  `"max_rounds"` `stop_reason` literal. A round-capped run on an unhealthy post-probe now correctly
  records `env_unhealthy` (validity mask). `safety_cap` is demoted to a backstop; the runner-level
  `max_steps` argument is superseded (ADR-0017).
- **Recorded policy on every trajectory** (`records/trajectory.py`, `records/serialize.py`):
  `Trajectory` gains `max_rounds`, `safety_cap`, `max_rounds_bound`, all round-tripped with safe
  defaults so any artifact proves whether it ran at 20 or 40.
- **Per-domain config** (`runners/round_budget.py`): default `max_rounds = {"F": 20, "D": 50}` with a
  per-task `metadata.max_rounds` override (task > domain; non-positive rejected). Threaded into
  `make_f_run_fn` and `dset_run` (which now records the configured `safety_cap`); B is config-only.
- **Aggregation split** (`experiments/aggregate.py`, §D.3): resource use (tokens/cost) summed over
  all runs incl. capped; time-to-completion (rounds/wall-time) right-censored; `n_censored` now counts
  `safety_cap_bound OR max_rounds_bound`.
- Retires the item-001 carry-forwards: serialize round-trips `max_rounds_bound` (CF1) and the censor /
  classifier now read it via direct attribute access (CF2).

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
