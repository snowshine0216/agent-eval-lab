# Item 004 — Failure classification + final evaluation report (exit gate)

Run: `coding-agent-eval` (Weeks 5-6) · Source row: MASTER-SPEC item 004 · Date: 2026-06-11
Brainstormed autonomously (no user in loop); every question auto-resolved with the
recommended answer, recorded in §Open questions below. Final item of the run: it owns
the code-world live-run wiring item 003 flagged (003-spec Non-goals / Open-questions 18),
the roadmap's "explicit classification of task, agent, and harness failures", the live
baseline runs over `code_repair_v1`, and the **final evaluation report** — the run's
user-stated exit gate.

## Goal

Close the Weeks 5-6 slice end-to-end:

1. **Code-world live-run wiring.** A pure, dataset-driven world resolver selects the
   tool registry, `apply` function, and effect-request executor per task from
   `available_tools`; `run_task_k` threads them into `run_single` (whose
   `apply_fn`/`executor` parameters already exist); `cli.run_baseline` stops
   hardwiring `WORKSPACE_TOOLS`. Workspace datasets run byte-identically to today.
2. **Failure classification.** A pure, total, versioned classifier
   (`reports/classify.py`, version `fc-v1`) maps every graded `RunResult` to exactly
   one of `passed | task_failure | agent_failure | harness_failure` plus a closed
   subcategory, reading only the mechanical discriminators the earlier items left:
   `evidence["execution"]` (`run | not_run | error`), `execution_error.kind`
   (`harness | tree_collision | verdict_missing | unknown`), suite `status`
   (`passed | failed | error | timeout | no_tests`), `trajectory.stop_reason` /
   `parse_failure`, and `grade.failure_reason` (`FailureCategory`). Classification is
   *derived, never stored*: the frozen `RunResult` schema is untouched.
3. **Live baseline runs.** `code_repair_v1` (15 tasks) × k=3 × 4 reachable conditions
   (`deepseek:deepseek-v4-pro`, `glm:Pro/zai-org/GLM-5.1`, `minimax:MiniMax-M3`,
   `local:Qwen/Qwen3-8B` via MLX) ≈ 45 runs/condition, temperature 0.0, cost capture;
   per-condition artifacts captured independently so one unreachable provider never
   blocks the others. `openrouter:gpt-5.5` is excluded (region/datacenter-IP ToS
   block, recorded in the roadmap).
4. **Final evaluation report (exit gate).** A `report-final` CLI command — pure build
   (`reports/final.py`) + markdown render, byte-deterministically regenerable from the
   committed run JSONLs — producing
   `docs/2026-06-11-coding-agent-eval/final-evaluation-report.md`: per-condition
   pass@1 / pass^3 with seeded cluster-bootstrap-by-task CIs, per-tier and
   per-capability breakdowns, the task/agent/harness classification table with
   per-category exemplars citing trajectory evidence, cost/latency, the v2 tool-use
   baseline context, a mechanical discriminativeness verdict, known limitations, and
   roadmap takeaways. The report is presented to the user at run close-out.

## Acceptance criteria

Each criterion is independently verifiable by a named test, a command, or inspection.

### A. Code-world live-run wiring

1. **World resolver.** A pure `resolve_world(available_tools) -> WorldBinding` (new
   small module `runners/worlds.py`) returns a frozen binding
   `(registry, apply_fn, executor)` from a closed two-entry table: workspace →
   (`WORKSPACE_TOOLS`, `workspace.apply`, `executor=None`); code →
   (`CODE_WORLD_TOOLS`, `code_world.apply`, the pytest executor of criterion 2).
   Resolution is by tool-name membership: every name must belong to exactly one
   world's registry and all of a task's tools must belong to the same world; an
   unknown name, a cross-world mix, or an **empty tool list** raises a
   `ValueError` naming the offending tools (fail loud, never a silent default —
   no shipped dataset has a tool-less task, verified across v1/v2/code_repair_v1,
   so empty has no data to define semantics for; grill Q4). Unit-tested on: pure
   workspace set, pure code set, mixed set, unknown name, empty set (expected:
   `ValueError`). A companion unit test pins the resolver's load-bearing
   invariant: `set(WORKSPACE_TOOLS) & set(CODE_WORLD_TOOLS) == set()` — a future
   tool name reused across worlds must fail CI, not silently make membership
   resolution ambiguous.
2. **Executor.** A `run_pytest`-backed executor satisfying loop.py's
   `Executor = Callable[[ExecutionRequest], ExecutionResult]` ships at the pytest
   edge: `execute_request(request) = run_pytest(request.files,
   timeout_s=DEFAULT_TIMEOUT_S)`. Timeout and interpreter remain edge policy
   (the `ExecutionRequest` carries only the tree, per CONTEXT.md). Integration-tested
   through `run_single` with a stub model client: a trajectory whose agent calls
   `run_tests` records a fulfilled `ToolSuccess` carrying a serialized
   `ExecutionResult` (ADR-0008: always `ToolSuccess`, whatever the suite status).
3. **`run_task_k` threading.** `run_task_k` accepts the world binding (or its
   `apply_fn`/`executor` fields) and passes them to `run_single`. Defaults preserve
   today's workspace behavior exactly: existing workspace tests pass unmodified, and
   a regression test asserts a workspace task graded through the new path yields a
   byte-identical serialized `RunResult` to the pre-change behavior.
4. **CLI wiring.** `cli.run_baseline` resolves the world per task via criterion 1 and
   no longer hardwires `WORKSPACE_TOOLS`. No new CLI flag: the dataset is the single
   source of world truth (rows are frozen append-only, so a metadata field is
   unavailable, and a flag could contradict the data). End-to-end test with a stub
   HTTP client: a `code_repair_v1` task runs through `run-baseline` machinery,
   fulfills a mid-trajectory `run_tests`, grades through the oracle edge, and streams
   a parseable `RunResult` line.
5. **Fail-loud reachability.** A connection failure (`httpx.ConnectError` or
   equivalent) surfaces as exit code 1 with a one-line message naming the provider id
   and `base_url`, plus a "is the server running?" hint for `local` — never a
   traceback mid-corpus. Tested with a refused-connection stub. Per-condition
   independence is structural: each condition is its own `run-baseline` invocation,
   the runs JSONL streams per task (already flushed), and `report-final` treats a
   partial condition as `incomplete` and a zero-record condition as `blocked`
   (validation-report precedent) — one dead provider never blocks the others.

### B. Failure classifier

6. **Module and shape.** `src/agent_eval_lab/reports/classify.py` exposes a pure
   `classify_run(run: RunResult) -> RunClassification` where `RunClassification` is a
   frozen dataclass `(category, subcategory, detail, classifier_version)`;
   `category ∈ {passed, task_failure, agent_failure, harness_failure}` (closed
   `Literal`), `classifier_version = "fc-v1"`, and `detail` is a one-line evidence
   citation (e.g. the colliding pair, the suite counts, the stop reason). The
   function is **total**: a Hypothesis property test feeds arbitrary evidence
   mappings / stop reasons and asserts it never raises and always returns a closed
   category. Classification is computed at report time only; no change to
   `RunResult`, its serializer, or captured artifacts.
7. **Mapping table.** The classifier implements exactly this priority-ordered table
   (first match wins; rows 2-16 are evaluated **only when `grade.passed` is
   false** — row 1 wins first, so a run that passes despite a recorded
   `parse_failure` classifies as `passed`; `exec_ev` = the evidence of the first
   execution leg, found at top level when `grade.grader_id == "execution"` or by
   recursing `evidence["sub_results"]` when `grader_id == "all_of"` — nested
   `AllOf` evidence is walked in declared order, reading the **plain dicts** the
   JSONL round-trip yields, never reconstructed dataclasses); every row has a
   dedicated unit test with a synthetic `RunResult`:

   | # | condition | category | subcategory |
   |---|-----------|----------|-------------|
   | 1 | `grade.passed` | passed | — |
   | 2 | `parse_failure` with error `"no choices in provider response"` | harness_failure | `provider_response` |
   | 3 | any other `parse_failure` (model emitted an unparseable payload) | agent_failure | `malformed_reply` |
   | 4 | `exec_ev["execution"] == "not_run"` (missing final_state) | harness_failure | `missing_final_state` |
   | 5 | `exec_ev["execution"] == "error"`, kind `harness` | harness_failure | `sandbox_fault` |
   | 6 | `exec_ev["execution"] == "error"`, kind `verdict_missing` | harness_failure | `verdict_missing` |
   | 7 | `exec_ev["execution"] == "error"`, kind `tree_collision` | agent_failure | `tree_collision` |
   | 8 | `exec_ev["execution"] == "error"`, **any other kind** (incl. `unknown`) | harness_failure | `foreign_verdict` |
   | 9 | `exec_ev` run, suite status `no_tests` | task_failure | `oracle_empty` |
   | 10 | `grade.failure_reason == "forbidden_action"` | agent_failure | `forbidden_action` |
   | 11 | `grade.failure_reason == "step_limit_exceeded"` | agent_failure | `step_limit_exceeded` |
   | 12 | `stop_reason == "max_steps"` (failed, budget truncated the attempt) | agent_failure | `step_exhaustion` |
   | 13 | `exec_ev` run, suite status `timeout` | agent_failure | `oracle_timeout` |
   | 14 | `exec_ev` run, suite status `failed` | agent_failure | `oracle_red` |
   | 15 | `exec_ev` run, suite status `error` | agent_failure | `oracle_error` |
   | 16 | fallback (failed, no rule above) | agent_failure | `other_miss` |

   ~~row 7: kind `unknown` → `foreign_verdict`~~ *(struck by grill Q1: the
   evidence `kind` is an OPEN string — `graders/execution._error_evidence` uses
   `getattr(value, "kind", "unknown")`, and a foreign value at a colliding hash
   carries its own `kind` (e.g. a `JudgeError`'s `transport`/`parse`), which
   would have fallen through rows 5-8 past 9/13-15 into row 16
   `agent_failure/other_miss` — a verdict-plumbing fault misfiled as an agent
   miss. Row 8 is now the error-branch fallback, closing the branch by
   construction; rows 7/8 swapped so the named kind precedes the fallback.)*

   ~~row 13: `sandbox_timeout`~~ *(renamed `oracle_timeout` by grill Q7: the
   timeout fires in the oracle run over the submitted tree, and conformance
   proves the reference solution passes the same oracle inside the same budget
   — the hang indicts the agent's code. `sandbox_*` names are reserved for
   harness faults, e.g. `sandbox_fault`.)*

   The row-2 discriminator is pinned mechanically (grill Q3): the literal
   `"no choices in provider response"` is hoisted to a shared constant in
   `records/trajectory.py` (schema-adjacent pure module; no record shape
   changes, so the frozen-interface constraint holds), referenced by both
   `runners/loop.py` and `reports/classify.py`, plus an integration test
   driving `run_single` against an empty-choices stub and asserting the
   recorded `parse_failure.error` equals the constant — the split cannot drift.

   Documented judgments inside the table (rendered as table footnotes in the
   report): row 7 — a canonical-prefix collision can only arise from a run's own
   write at a path colliding with an oracle module's canonical form: oracle paths
   are disjoint from every initial-tree path (ADR-0012's conformance contract,
   whose consequences pre-authorize this row), code-world has no delete tool (the
   final tree is initial ∪ agent writes), and exact-path equality is displacement,
   never collision (ADR-0010, `prefix_collision` returns false on equality) — the
   judgment is therefore conditional on the dataset's conformance contract, which
   holds for the whole code-repair lineage; row 9 — conformance proves every
   shipped oracle collects ≥ 1 test (003 criterion 8) and the overlay always
   contributes the oracle files (a collection-breaking agent write yields status
   `error`, pytest exit 2, never `no_tests`), so an empty oracle at grading time
   indicts the task data; row 4 — the runner always seeds `final_state` from
   `initial_state`, so its absence is a wiring defect; row 12 outranks 13-15
   because a budget-truncated attempt's red oracle is an artifact of the
   truncation — and the budget itself is data-validated (per-task
   `metadata.max_steps` honored via `effective_max_steps`, ADR-0004 wiring
   already landed; conformance floors the budget), so exhaustion is the agent's
   spend, not harness starvation; row 3 — message-level emptiness ("assistant
   message has neither content nor tool_calls") stays agent-side: the provider
   envelope was well-formed, the model's own message was unparseable.
8. **Taxonomy untouched.** `FailureCategory` gains no new values; a test asserts the
   literal's member set is unchanged. The task/agent/harness axis lives only in
   `RunClassification` — it is an interpretation layer over grades, not a grade.
9. **Task-defect review queue (report-level, not per-run).** The report builder
   computes "task-defect candidates": task ids failing **all recorded runs on
   every non-blocked condition that has records for the task** (grill Q10: an
   incomplete condition with zero records for a task contributes nothing to that
   task's unanimity — no fabricated evidence; blocked conditions are excluded
   entirely). The rendered queue cites per-task evidence strength
   (`n_conditions`, `n_runs`) so a reviewer sees how unanimous "unanimous" was.
   These are *flagged for human review*, never auto-classified as `task_failure`
   — the conformance suite already proves solvability, oracle breadth, and
   symptom reality, so a unanimous failure defaults to "hard, not defective"
   pending adjudication. Unit-tested (unanimous-fail, one-condition-passes,
   blocked-condition-excluded, missing-records-on-one-condition cases).
10. **Pinned harness residuals (documentation, not detection).** The report's known-
    limitations section names, with citations: (a) the `graders/policy.py` dotted-
    path false-allow — an agent minting a fresh extension path at run time (e.g.
    writing `app.py.bak` under an `app.py` allowlist) is silently *passed*, a
    missed-detection bias the per-run classifier cannot see (003-spec criterion 16);
    (b) `pytest_edge` `shutil.rmtree(ignore_errors=True)` can silently leak sandbox
    dirs, and a disk-full `OSError` mid-materialize is captured as an
    `ExecutionError(kind="harness")` by the oracle edge — the worked example of a
    `sandbox_fault` harness failure (001-review notes).

### C. Live baseline runs

11. **Run matrix.** `run-baseline --dataset examples/datasets/code_repair_v1.jsonl`
    executed for the four reachable conditions — `deepseek`, `glm`, `minimax`, and
    `local` with `--model Qwen/Qwen3-8B` (matching the Weeks 3-4 condition id
    `local:Qwen/Qwen3-8B` for cross-week comparability) — at `--k 3`,
    `--temperature 0.0`, default prompt config (no `--system-prompt-file`; slug
    untagged per ADR-0007). Each condition writes ~45 records (15 tasks × 3).
12. **Working artifacts do not clobber Weeks 3-4.** Live runs write to
    `--out reports/code-repair/` — the v2 artifacts in `reports/` share the same
    condition slugs (`runs-deepseek-deepseek-v4-pro.jsonl`, …) and remain the only
    regeneration source for the committed Weeks 3-4 reports; overwriting them is
    forbidden.
13. **Committed run artifacts.** The four runs JSONLs are copied to
    `docs/2026-06-11-coding-agent-eval/runs/runs-<condition-slug>.jsonl` and
    committed. This deliberately extends the Weeks 3-4 convention (which committed
    only rendered reports): the exit gate claims byte-deterministic regeneration
    *from captured runs*, and that claim is only reviewer-verifiable when the runs
    are in the repo. No `.gitignore` conflict (grill Q6, verified with
    `git check-ignore`): `/reports/` and `/runs/` are root-anchored patterns, so
    the run-dir `runs/` subdirectory is committable as-is. Because the JSONLs
    embed agent solution trees (`final_state`) and oracle stdout, they join the
    Weeks 9-10 **never-train manifest** beside the review-fixtures sidecar (the
    003 precedent). Size is bounded (15 tasks, head-capped canonicalized output;
    single-digit MB total). Every committed line parses through the existing
    `_load_run_results` loader (round-trip test on a sample of each file).
14. **Cost capture.** Token usage rides every trajectory (already recorded);
    per-condition prices live in a committed
    `docs/2026-06-11-coding-agent-eval/prices.json` with the pinned shape
    (grill Q11) `{"snapshot_date": "YYYY-MM-DD", "prices": {"<condition_id>":
    {"input_per_mtok": float, "output_per_mtok": float}}}`; conditions absent
    from the map (e.g. `local`) render as "not computed". A partial or
    unreachable condition is recorded as `incomplete`/`blocked` in the report
    with its reason — runs for the other conditions proceed and are committed
    regardless.

### D. Final evaluation report (exit gate)

15. **Command.** A new `report-final` subcommand: inputs
    `--runs LABEL=condition_id=path` (one per condition, C1-C3 hosted / C4 local,
    the report-validation label convention), `--dataset`, `--tiers`, `--prices`,
    `--context-file`, `--k 3`, `--expected-n-tasks 15`, `--seed 20260610`,
    `--n-resamples 2000`, `--alpha 0.05`, `--out`. Unlike `report-validation`
    (whose parser discards the middle `condition_id` segment — verified in
    `cli._parse_runs_spec`), `report-final` makes it live (grill Q11): each
    condition's `condition_id` is **derived from its records**, a heterogeneous
    runs file is a loud error, and when the middle segment is present it is
    cross-checked against the records (mismatch = exit 1, no silent
    mislabeling) — the prices lookup joins on this derived id. Pure build
    (`reports/final.py: build_final_report`) + pure `render_markdown`; file I/O and
    JSON parsing stay in `cli.py`; output written atomically (`_atomic_write`
    precedent). No model calls, no subprocess: the command is replay-only over
    captured runs.
16. **Report sections.** The rendered report contains, in order: (1) header —
    dataset id, n=15, k, conditions, bootstrap seed, classifier version `fc-v1`,
    and the temperature-honesty note (the Weeks 3-4 wording: only the bootstrap RNG
    is seeded); (2) per-condition pass@1 / pass^3 with 95% cluster-bootstrap-by-task
    CIs and status (`complete | incomplete | blocked`); (3) per-tier pass^3;
    (4) per-capability pass^3; (5) **failure classification** — per condition, a
    category × subcategory count table over all failing runs, plus per-category
    exemplars (deterministic: lex-first task id, lowest run_index) citing task id,
    run_index, and the discriminator evidence (suite counts / error kind / stop
    reason / colliding pair); (6) task-defect candidates (criterion 9), "none" when
    empty; (7) cost and latency per condition — prompt/completion tokens, cost USD
    where priced, mean run latency; (8) context — the `--context-file` text rendered
    verbatim under "Context: prior baselines (workspace_tool_use v1/v2)";
    (9) discriminativeness verdict; (10) known limitations; (11) roadmap takeaways;
    (12) excluded conditions — `openrouter:gpt-5.5` with the region/ToS reason.
    The report carries **no generation timestamp** anywhere (grill Q5, the
    Weeks 3-4 validation-report precedent): time-like values appear only as
    *recorded data* — mean latency summed from trajectory `usage.latency_s`,
    the `prices.json` snapshot date — and the footer's regeneration command is
    static text, so build+render stays a pure function of its inputs.
17. **Discriminativeness verdict.** The mechanical Weeks 3-4 rule, reused (shared or
    extracted from `reports/validation.py`, not re-invented): weak rung = hosted
    conditions differ on ≥ 1 task AND ≥ 1 hosted pass^3 < 1.000; strong rung = a
    hosted pair separated by a paired cluster-bootstrap CI excluding 0, or a
    non-trivial monotone tier gradient; near-misses, skipped pairs, and the n=15
    honesty line ("intervals are wide; absence of separation is not evidence of no
    separation") are rendered. Any extraction refactor of `reports/validation.py`
    must keep `report-validation` output **byte-identical** over a fixture run
    set (grill Q12: the committed Weeks 3-4 reports are regenerable artifacts;
    a drifting render would orphan them), proven by a regression test.
18. **Known limitations (pinned list).** At minimum: ADR-0010 residual trust
    boundary (oracle imports agent-authored modules in-process; import-time code
    runs); sandbox isolation is temp-dir-and-convention, not kernel-level (no
    containers); n=15 tasks → wide CIs, dev split only; the policy dotted-path
    false-allow residual (criterion 10a); the rmtree/disk-full harness notes
    (criterion 10b); hosted providers are not greedy-deterministic at temperature 0;
    `openrouter:gpt-5.5` unreachable (network policy, not harness).
19. **Byte-deterministic regeneration.** Running `report-final` twice over the
    committed runs JSONLs (criterion 13) with the pinned seed produces byte-identical
    output, and that output is byte-identical to the committed
    `docs/2026-06-11-coding-agent-eval/final-evaluation-report.md` (verified by
    `diff` at final-verify; the exact regeneration command is recorded in the report
    footer). A unit test asserts build+render determinism over a fixture run set.
    Determinism scope (grill Q5): **nothing is excluded** from the byte claim —
    there is no "generated at" line to exempt; latencies and costs are
    deterministic functions of recorded usage data and the committed prices
    file, mirroring the Weeks 3-4 convention.
20. **Exit-gate artifact.** `final-evaluation-report.md` is committed in the run dir
    (never gitignored), generated from real live-run data (no fabricated numbers:
    blocked conditions render as blocked), and is presented to the user at run
    close-out per the MASTER-PLAN run-level exit. The report renders correctly with
    a blocked condition present (tested with an empty-runs fixture).

### E. Engineering gates

21. **TDD evidence.** Red-green per CLAUDE.md: the world-resolver, executor,
    threading, classifier (every mapping row), report builder, and renderer tests
    land before their implementations; the item's history shows failing-first
    commits or equivalent red-green notes in the implementation log.
22. **CI and style.** All new tests run in the default pytest lane with no live
    model calls and no new CI lane (the only subprocess use is via the existing
    `run_pytest` in integration tests, within the established CI budget);
    `uv run ruff check .` and `uv run ruff format --check .` stay clean; new modules
    follow functional core / imperative shell (classify and report builders pure;
    I/O confined to `cli.py` and the existing edges).

## Non-goals

- **New `FailureCategory` values or `RunResult`/`GradeResult` schema changes.** The
  task/agent/harness axis is a derived interpretation (`RunClassification`), not a
  stored grade field (criterion 8).
- **Editing `code_repair_v1` or its sidecars.** The dataset is frozen append-only;
  a live-run-discovered task defect lands in the task-defect candidates section and
  the run log, and would ship as a future dataset version — never an edit.
- **Fixing the `graders/policy.py` dotted-path residual or the workspace graders.**
  Documented as a harness limitation (criterion 10a); touching the frozen grader is
  out of scope.
- **Kernel-level sandboxing / containers, per-test process isolation** — inherited
  001/002 non-goals; documented in limitations.
- **A prompt-config comparison** (planning vs default) — Weeks 3-4 delivered that
  pattern; this slice runs the default config only.
- **`LlmJudgeSpec` legs, judge calibration** — no Tier-3 grading on code tasks.
- **Multi-config experiment machinery, Holm/Bonferroni, Inspect AI conformance** —
  Weeks 7-8.
- **Failure mining into new tasks, leakage-safe splits** — Weeks 9-10 (the
  classifier's output is their input).
- **`openrouter:gpt-5.5` runs or proxy work** — excluded with the documented
  network reason; reported, not retried.
- **A generic multi-provider orchestrator command** (run-all-conditions): four
  explicit invocations keep per-condition independence and match the existing
  runbook shape.

## Constraints

- **Frozen interfaces.** `RunResult`, `GradeResult`, `FailureCategory`,
  `Trajectory`, the runs-JSONL line format, and `condition_id = provider:model` are
  unchanged; `run_task_k`'s new parameters must default to today's workspace
  behavior (criterion 3's byte-identical regression).
- **Append-only dataset and sidecars** — `code_repair_v1.jsonl`,
  `*_tiers.json`, `*_review_fixtures.json` are read-only inputs.
- **Functional core / imperative shell.** `classify.py` and `reports/final.py` are
  pure and total; subprocess I/O stays behind `pytest_edge`; HTTP stays behind
  `client.py`; file I/O stays in `cli.py`.
- **Reproducibility.** The only seeded knob is the bootstrap RNG (seed 20260610,
  2000 resamples, α=0.05 — the Weeks 3-4 conventions); report regeneration is a pure
  replay of committed artifacts (criterion 19); live-run nondeterminism (provider
  sampling) is measured by k=3 + pass^3, never claimed away.
- **Artifact hygiene.** `reports/` stays gitignored (working copies only, under
  `reports/code-repair/`); committed copies live in the run dir
  (`docs/2026-06-11-coding-agent-eval/runs/`, `prices.json`, `v2-context.md`,
  `final-evaluation-report.md`). Weeks 3-4 artifacts in `reports/` are never
  overwritten (criterion 12).
- **Security.** No API keys in code, artifacts, or the report (env-var names only);
  oracle test content appears in committed run JSONLs only inside grade evidence
  hashes/statuses — never rendered into the report body beyond test ids and counts;
  webhook/proxy URLs never ride CLI positional args.
- **Cost bound.** ~180 live runs total (≈45/condition) at 15 small tasks; hosted
  spend is bounded by the prices.json snapshot's estimate; the local condition
  requires the MLX server up before its invocation (criterion 5's loud failure
  otherwise).
- **CI budget.** New integration tests add only a handful of sandboxed `run_pytest`
  invocations; the default lane stays within the established wall-time budget.
- **Branch flow.** Work lands on `claude/coding-agent-eval-004`, PR into
  `autodev/coding-agent-eval-feature`, squash-merge on gate pass; the feature branch
  is never merged to `main` by autodev (user lands it at close-out).

## Open questions resolved during brainstorming

Autonomous mode: each question was answered with the recommended option; rationale
recorded here in lieu of user confirmation.

1. **How does the runner know a task is code-world — metadata field, dataset flag,
   CLI flag, or derived from the row?** → Derived from `available_tools` via a pure
   resolver (criterion 1). A `world` metadata field is unavailable: `code_repair_v1`
   rows are frozen append-only, and retrofitting the field means editing 15 frozen
   rows. A CLI flag can contradict the data and adds a mis-set surface. Tool-name
   membership is already authoritative (003 conformance pins each task's toolset),
   collision-free across the two worlds, and per-task — a future mixed dataset works
   unchanged.
2. **Where does the classifier live, and is classification stored on records?** →
   `reports/classify.py`, derived at report time only. Storing it would touch the
   frozen `RunResult` schema, orphan already-captured artifacts, and freeze
   classifier semantics into data; deriving keeps a classifier-version bump a pure
   re-render (no re-running models). The module sits in `reports/` because the
   report path is its only consumer this slice; Weeks 9-10's
   agent-vs-evaluation-defect report imports it from there.
3. **What exactly maps to task vs agent vs harness?** → The criterion-7 table,
   priority-ordered and total. Harness = the evaluation system failed to produce a
   trustworthy verdict (sandbox infra fault, verdict plumbing, provider response
   malformed, missing final state). Task = the task data is defective at grading
   time (`no_tests` oracle — the only mechanically detectable post-conformance task
   defect). Agent = everything the run itself did wrong (red/erroring oracle,
   hanging code, policy breaches, unparseable replies, budget exhaustion,
   tree-colliding writes). A fifth "unknown" class was rejected: rows 12-16 make
   the function total without one, and an unknown bucket invites lazy triage.
4. **Is `tree_collision` agent or harness?** → Agent (`agent_failure/tree_collision`),
   as a documented judgment row. Oracle paths are disjoint from every initial-tree
   path (ADR-0012), so a canonical-prefix collision can only be minted by the run's
   own write — either an unnecessary file outside any task requirement or a
   shadow-the-oracle attempt (the ADR-0010 reward-hack vector). The report renders
   the judgment as a footnote so a reviewer can re-litigate it with the cited
   evidence.
5. **Is a `parse_failure` agent or harness?** → Both, split on the recorded error:
   `"no choices in provider response"` is the provider/transport failing to deliver
   a well-formed completion (harness — the model under test never got to act on the
   turn), while any other parse failure is the model emitting an unparseable payload
   (agent — the capability failure `malformed_call` already names in the workspace
   taxonomy). The discriminator is mechanical: the loop records distinct error
   strings for the two sources. *(Sharpened by grill Q3: the literal is hoisted
   to a shared constant in `records/trajectory.py` and pinned by a stub-loop
   test — see criterion 7.)*
6. **How are residual task defects detected post-conformance?** → Two channels:
   the mechanical `no_tests` rule (table row 9), and the report-level unanimous-
   failure review queue (criterion 9) that *flags without classifying*. Conformance
   already proves solvability/breadth/symptom mechanically, so any blanket
   "all models failed ⇒ task defect" rule would misclassify genuinely hard tasks —
   exactly the corruption the Weeks 3-4 discriminativeness work warns against.
   Human adjudication is the only sound resolver at n=15; the queue makes it cheap.
7. **Report command: extend `report-validation` or a new command?** →
   New `report-final`. The validation report answers "is the dataset fit for
   purpose"; the final report answers "what did the evaluation find" — different
   sections (classification, cost, context, takeaways), different exit criteria.
   Overloading one builder with mode flags was rejected (two reports' invariants
   tangled in one function). Shared pieces (CI machinery, discriminativeness rule,
   label convention) are reused by import/extraction, not duplication.
8. **Report location and name?** →
   `docs/2026-06-11-coding-agent-eval/final-evaluation-report.md`, committed — the
   exit-gate artifact mirrors `validation-report.md`'s run-dir placement. Top-level
   `reports/` was rejected: gitignored by design.
9. **Are the live-run JSONLs committed, and where?** → Yes —
   `docs/2026-06-11-coding-agent-eval/runs/`, with working copies in gitignored
   `reports/code-repair/`. This deliberately diverges from Weeks 3-4 (runs stayed
   only in gitignored `reports/`, leaving the byte-determinism claim verifiable
   only on this machine): the exit gate's regeneration claim must be checkable by a
   reviewer from the repo alone. Size is bounded (15 tasks, output head-capped at
   the edge). The `reports/code-repair/` subdirectory also prevents slug collisions
   from overwriting the v2 run artifacts that back the committed Weeks 3-4 reports.
10. **Where do prices come from for the cost section?** → A committed
    `prices.json` keyed by `condition_id`, passed via `--prices`; absent conditions
    render "not computed" (the `local` MLX condition has no marginal token price).
    Re-using `run-baseline`'s per-invocation price flags was rejected: the final
    report aggregates four conditions and must regenerate from data, not from
    remembered flag values.
11. **How does the v2-baseline comparison stay byte-deterministic?** → A committed
    `v2-context.md` injected verbatim via `--context-file` (the
    `--planning-prompt-file` precedent from `compare-configs`). Hand-editing the
    rendered report breaks regeneration; baking prose into the renderer makes
    context edits code changes. Cross-dataset numeric comparison (workspace pass^3
    vs code pass^3) is presented as *context*, never as a paired statistic — the
    task universes differ, so no CI is computed across them.
12. **Bootstrap conventions?** → Identical to Weeks 3-4: seeded
    cluster-bootstrap-by-task percentile CIs, seed 20260610, 2000 resamples,
    α=0.05, paired diffs only over identical task universes, reusing
    `metrics/reliability.py` unchanged. A fresh seed for this run was rejected:
    cross-run convention stability beats date-vanity, and the value is a CLI
    default, not a hidden constant.
13. **Discriminativeness rule for the code slice?** → The Weeks 3-4 mechanical rule
    verbatim (criterion 17), shared with `reports/validation.py` rather than
    re-specified. Inventing a code-specific rule was rejected: the estimand
    (hosted-condition separation) is identical, and rule drift would make the two
    reports' verdicts incomparable.
14. **How is local-MLX reachability handled?** → Fail loud, per condition: a
    connection error exits 1 with provider id + base_url + a start-the-server hint
    (criterion 5). A silent skip was rejected (fabricates a blocked condition out
    of an operator error); an HTTP pre-flight probe endpoint was rejected as
    redundant — the first chat call *is* the probe, and the streamed JSONL
    preserves any partial progress for `incomplete` reporting.
15. **k and temperature?** → k=3, temperature 0.0 — matching every prior baseline so
    pass@1/pass^3 are cross-week comparable; ~45 runs/condition keeps hosted spend
    and local wall-time bounded. k=5 was rejected: it changes the reliability
    estimand mid-program for no decision-relevant gain at n=15.
16. **Does `run-baseline`'s per-condition baseline report change?** → No. The
    existing `baseline-*.md` outputs continue as working artifacts; the final
    report is the only new rendered surface. Touching the v1-era baseline renderer
    risks byte-drift on a frozen, already-exercised path.
17. **Subcategory vocabulary — open or closed?** → Closed, 15 values (criterion 7's
    table), versioned with the classifier (`fc-v1`). An open string field was
    rejected: the Weeks 9-10 failure-mining work needs stable categories to mine
    against, and free-form strings fracture counts exactly the way CONTEXT.md's
    provenance lesson warns. *(Grill Q7 renamed one value —
    `sandbox_timeout` → `oracle_timeout` — count unchanged at 15.)*

## Grill session — resolved decisions (2026-06-11)

Autonomous grill (grill-with-docs, no user in loop); every question resolved with
the recommended answer, verified against the code surfaces named below. Docs
synced inline: CONTEXT.md (terms **RunClassification (failure classification)**,
**world binding**, **task-defect candidate**; cross-ref added to
**FailureCategory**) and ADR-0013 (the fc-v1 classification decision).

- **Q1 — Row "kind `unknown`" leaked foreign kinds into agent rows.**
  `graders/execution._error_evidence` reads `getattr(value, "kind", "unknown")`
  — an open string. A foreign value at a colliding hash carries its *own* kind
  (`JudgeError.kind ∈ {transport, parse, …}`), which matched no error row and
  fell through to `agent_failure/other_miss`. Resolved: the error branch closes
  with an any-other-kind fallback → `harness_failure/foreign_verdict` (rows 7/8
  reordered). The Hypothesis totality test gains an explicit foreign-kind case.
- **Q2 — `tree_collision → agent` is sound under ADR-0012.** Three mechanical
  facts: conformance bans oracle paths equal/prefix-colliding with any
  initial-tree path; code-world has no delete tool (final tree = initial ∪ agent
  writes); exact equality is displacement, not collision (`prefix_collision`
  returns false on equality). So a collision pair always involves an
  agent-minted spelling. ADR-0012's consequences pre-authorize the row; the
  footnote now states the judgment is conditional on the conformance contract
  (holds for the code-repair lineage).
- **Q3 — Parse-split criterion was a magic string.** The harness/agent split
  keyed on a literal duplicated from `runners/loop.py`. Resolved: shared
  constant in `records/trajectory.py` (no record-shape change; frozen-interface
  constraint holds) + a stub-loop test pinning the recorded error. Judgment
  recorded: message-level emptiness stays agent-side.
- **Q4 — World resolver: empty tool list pinned to `ValueError`.** No shipped
  dataset has a tool-less task (verified v1=20, v2=50, code_repair_v1=15 rows);
  fail loud beats inventing semantics with no data. Registry-name disjointness
  (workspace 9 names ∩ code 4 names = ∅, verified) becomes a tested invariant.
  No schema-ADR conflict: resolution reads only the frozen `available_tools`.
- **Q5 — Byte-determinism scope made explicit.** No generation timestamp
  anywhere (Weeks 3-4 precedent: `reports/validation.py` renders none);
  time-like values only as recorded data (usage latency sums, prices snapshot
  date); nothing exempted from the byte claim.
- **Q6 — Committed run JSONLs conflict with no repo convention.**
  `git check-ignore` verified `/reports/` and `/runs/` are root-anchored;
  `docs/<run-dir>/runs/` is committable unchanged. New obligation: the JSONLs
  embed agent solution trees and oracle stdout, so they join the Weeks 9-10
  never-train manifest (003 sidecar precedent).
- **Q7 — `sandbox_timeout` renamed `oracle_timeout`.** The timeout fires in the
  oracle run over the submitted tree and conformance proves the reference
  solution finishes inside the same budget — the hang indicts the agent's code;
  `sandbox_*` is harness vocabulary (`sandbox_fault`). Vocabulary stays 15.
- **Q8 — Implicit pass guard made explicit.** Rows 2-16 evaluate only when
  `grade.passed` is false; a run that passes despite a recorded `parse_failure`
  (e.g. state already satisfying the spec before the failed turn) is `passed`.
- **Q9 — `exec_ev` walk reads round-tripped dicts.** `sub_results` entries are
  plain dicts post-JSONL (`composite.py` serializes nested evidence as dicts);
  the walk is specified over dict keys (`grader_id`, `evidence`), first
  execution leg in declared order, recursing nested `all_of` entries.
- **Q10 — Task-defect unanimity under incomplete conditions pinned.** Unanimity
  quantifies over non-blocked conditions *with records for the task*; the queue
  renders per-task `n_conditions`/`n_runs` so evidence strength is visible. No
  invented minimum-condition threshold.
- **Q11 — `--runs` middle segment goes live; prices schema pinned.**
  `cli._parse_runs_spec` discards `condition_id` today; `report-final` derives
  it from records (heterogeneous file = loud error), cross-checks the segment
  when present, and joins `prices.json`
  (`{"snapshot_date", "prices": {condition_id: {input_per_mtok,
  output_per_mtok}}}`) on the derived id.
- **Q12 — Extraction must not byte-drift the frozen validation report.** Any
  sharing/extraction of the discriminativeness rule keeps `report-validation`
  output byte-identical over a fixture set, proven by a regression test — the
  committed Weeks 3-4 reports are regenerable artifacts.
- **Q13 — Row 12 (`step_exhaustion` = agent) upheld.** The budget is
  data-validated (per-task `metadata.max_steps` honored via
  `effective_max_steps` — ADR-0004 wiring already landed in
  `runners/multi_run.py` — and conformance-floored), so exhaustion is the
  agent's spend; the validation report's "starvation suspects" lens remains in
  working artifacts. Footnote sharpened.
- **Q14 — ADR scope: one ADR.** fc-v1 classification = ADR-0013 (three-of-three:
  semantics anchor Weeks 9-10 mining and Release #1; tree_collision→agent /
  parse split / no-unknown-bucket are surprising; derived-vs-stored and
  queue-vs-auto-defect were real trade-offs). World resolver and committed-runs
  divergence stay spec-level resolved decisions (reversible; two-of-three).
- **Q15 — Hypothesis dependency verified present** (`pyproject.toml`
  `hypothesis>=6.100`): criterion 6's property test adds no new dependency, no
  CI-lane change.
