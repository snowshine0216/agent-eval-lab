# Item 004 — Validation + failure-mode report + two-configuration comparison

- **Run:** `docs/2026-06-10-dataset-grader-quality`
- **Date:** 2026-06-10
- **Realizes (roadmap Weeks 3-4):** "a failure-mode report; a comparison of two
  agent configurations" + the statistics focus (probability / random variables,
  expectation / variance, estimators and confidence intervals) + the binding
  **USER DIRECTIVE**: *"After all validation is required to run the report for me
  to review"* — the terminal deliverable is **live runs + committed reports the
  user reads**, not just green gates.
- **Realizes (design doc):** §4.6 estimand discipline (pass^k as the task-level
  reliability estimand; the *task* is the resampling unit because the k runs of
  a task move together — cluster bootstrap by task), §3 (one OpenAI-compatible
  client, many provider configs — reused as-is for the live runs).
- **Blocking contract consumed:** **ADR-0004** — thread per-task
  `metadata.max_steps` through `multi_run.py` / `cli.py` *before any live v2 run*.
  Without it every T3/T4 task hits `stop_reason="max_steps"` and grades as a
  step-limit failure that *looks like an agent failure but is harness
  starvation* — the precise agent-vs-harness confound the conformance floor
  (item 002: every T3/T4 task sets `max_steps >= dependent_calls + 2`) exists to
  prevent. This item honors the floor by wiring the budget.
- **Depends on (already merged):** item 001 (composite verification, final-state
  threading, `forbidden_action` / `step_limit_exceeded` categories, JSONL
  parsing), item 002 (`workspace_tool_use_v2.jsonl` — the frozen 50-task set, the
  taxonomy / rubric / review-ledger, the per-task `max_steps` data + conformance
  floor), item 003 (`llm_judge` grader + calibration — **not exercised here**;
  the v2 set grades deterministically). Reuses the Weeks 1-2 `run-baseline`
  command, `reports/baseline.py`, `metrics/{reliability,cost,agreement}.py`, the
  `runners/{multi_run,loop,config}.py` runner, and the streaming-JSONL
  per-task-survival pattern (commits 7a651bc / c744b5f).

## Goal

Close Weeks 3-4 by **running the v2 dataset live** across every reachable model
condition (k=3), then producing two committed Markdown deliverables the user
reviews: (1) a **failure-mode report** that answers the headline question — *did
v2 draw a capability boundary between strong models that v1 saturated?* — and
(2) a **pre-declared two-agent-configuration comparison** with an
estimator-and-CI treatment honest about n=50. All harness gates (pytest, `ruff
check`, `ruff format`) stay green, and the runner finally honors the ADR-0004
per-task step budget so the live numbers measure the *model*, not the harness.

This item ships the minimum new code needed to make the live runs trustworthy
and the reports honest: the ADR-0004 wiring, a cluster-bootstrap-by-task
estimator in pure metrics code, a system-prompt knob for the comparison, and a
pure validation/comparison report builder. It is explicitly **Weeks 3-4 scale**
— it does *not* build the Weeks 7-8 `ExperimentSpec` machinery, multiple-testing
control, or held-out splits; those are named as non-goals below.

## The two-configuration comparison (PRE-DECLARED — frozen before any run)

The roadmap deliverable is "a comparison of *two agent configurations*." Of the
candidates — (a) same model, two system prompts; (b) same model, with/without
distractor tools; (c) two models — **(a) is chosen**: it is the cleanest reading
of "two *agent* configurations" (the model and dataset are held fixed; only the
agent's instruction harness varies), it isolates a single real agent knob, and
it does not duplicate the multi-condition validation (which already covers the
two-models reading) nor mutate the frozen v2 dataset (which (b) would, making it
a dataset knob not an agent config).

**Configuration A — `default`:** the system prompt already carried in each
task's `input.messages[0]` (the v2 author's prompt), used unchanged.

**Configuration B — `planning`:** the same task's system turn replaced with a
planning-encouraging prompt that instructs the agent to think step by step and
enumerate the tickets/accounts it intends to touch *before* modifying state
(e.g. *"Before calling any tool that changes state, first list the tickets or
accounts you will act on and why; do not modify anything you have not first
identified."*). The exact text is fixed in the spec/plan and committed as a
fixture; it is the *only* difference between the two configurations.

- **Held fixed:** model = `deepseek:deepseek-v4-pro` (the cheapest reliable
  hosted frontier model; one model keeps the comparison a clean agent-config
  contrast and the token spend bounded), dataset = `workspace_tool_use_v2`
  (all 50 tasks, paired), k=3, temperature=0.0, per-task `max_steps`,
  registry = `WORKSPACE_TOOLS`.

- **Hypothesis (directional, frozen before running):** Configuration B
  (`planning`) achieves a **higher pass^3 on the hard tiers (T3+T4)** than
  Configuration A, because the v1/v2 failure signal is *over-calling and
  mis-tracking derived/minted ids on multi-step chains* (v1: local Qwen3-8B
  appended a redundant `update_ticket` on the two multi-step tasks); an explicit
  "identify before you modify" step is expected to suppress `extra_call` and
  `wrong_args` on `multi_step_state` / `derived_reasoning` / `constraint_compliance`
  tasks. On T1+T2 the two configs are expected to be **statistically
  indistinguishable** (both near-ceiling; planning cannot help where there is no
  multi-step reasoning to plan).

- **Primary metric:** **pass^3 on the paired 50 tasks**, reported per
  configuration and as the **paired difference Δ = pass^3(B) − pass^3(A)** with a
  **cluster-bootstrap-by-task 95% CI** on Δ (resample the 50 tasks with
  replacement; both configs' k=3 outcomes for a resampled task move together —
  the pairing is preserved within a resampled task).

- **Secondary metrics (reported, not decisive):** pass@1; the per-tier pass^3
  split (the place the hypothesis actually lives); `extra_call` rate and
  `wrong_args` rate (the mechanism the hypothesis predicts); total cost (planning
  prompts cost more tokens — the trade-off is reported honestly).

- **Decision rule (frozen before running):**
  - If the **Δ pass^3 (T3+T4) 95% CI excludes 0 and lies above 0** → verdict
    **"planning helps on hard tiers"** (hypothesis supported).
  - If the CI **includes 0** → verdict **"no detectable effect at n=50"**, and
    the report states the CI width honestly (with 50 tasks and near-ceiling rates
    the interval is wide; absence of a detectable effect is *not* evidence of no
    effect, and the report says so in those words).
  - If the CI **excludes 0 and lies below 0** → verdict **"planning hurts"** (the
    pre-registered surprise outcome — reported as found, never massaged).
  - The verdict is read mechanically off the CI; it is **not** chosen after
    seeing the point estimate.

## Live validation conditions (frozen)

| condition | provider:model | keyed in `.env`? | role |
|---|---|---|---|
| C1 | `deepseek:deepseek-v4-pro` | `DEEPSEEK_API_KEY` ✅ | hosted frontier (also the comparison base) |
| C2 | `glm:Pro/zai-org/GLM-5.1` | `SILICONFLOW_API_KEY` ✅ | hosted frontier |
| C3 | `minimax:MiniMax-M3` | `MINIMAX_KEY` ✅ | hosted frontier |
| C4 | `local:Qwen/Qwen3-8B` (MLX @ localhost:11434) | n/a (free) | weak-model contrast |
| — | `openrouter:openai/gpt-5.5` | — | **OUT** — see SKIPPED.md (network ToS block, environmental) |

- **k=3** per the established pass^3 methodology (matches v1: 150 runs/condition).
- **`local` model-id fix:** `config.py` registers `model_id="qwen3-8b"` but the
  MLX server serves `Qwen/Qwen3-8B` (confirmed up, `/v1/models`). The live run
  passes `--model Qwen/Qwen3-8B` (the existing `run-baseline --model` override) —
  a **runtime flag, not a code change** to the frozen registry. The plan MAY
  alternatively correct the registry default; either way the condition id in the
  report reads `local:Qwen/Qwen3-8B`.
- **Run order:** hosted first (C1–C3, fast, cents each), local last (C4, free but
  wall-clock-dominant: 50 tasks × 3 runs × up-to-6-step chains on an 8B MLX model
  may run long — acceptable because it is free and the harness streams per task,
  so a mid-run failure never loses completed work). Each condition writes its own
  `runs-<condition-slug>.jsonl` (per-condition artifact naming, commit c744b5f).
- **Blocked-condition handling:** if a condition is entirely unreachable at run
  time (key unset, endpoint down), the report marks it **blocked** with the
  reason — exactly as v1 reported openrouter — and never fabricates numbers.
  Per-run provider errors are recorded in the streamed JSONL (existing behavior),
  never invented.

## Architecture (minimum new code, pure core + thin edge)

**ADR-0004 wiring (the blocking contract):**
- `runners/multi_run.py` — `effective_max_steps(task, default)` (pure):
  returns `task.metadata.max_steps` when present, else the CLI default. Threaded
  into `run_single`. Per-task budget **wins** when present; the CLI `--max-steps`
  is the **default for tasks without one**, never a cap (justified below).
- `cli.py` `run_baseline` — pass the per-task budget through the loop, not a
  single global value.

**System-prompt knob (the comparison's only varying input):**
- `runners/prompt.py` (**new, pure**) — `apply_system_prompt(messages, prompt) ->
  tuple[MessageTurn, ...]`: returns a new message tuple with the leading `system`
  `MessageTurn` replaced (or prepended if none) by `prompt`; non-mutating
  (spread/rebuild, never in-place). This is the *entire* "Condition extension" —
  no `Condition` class, no `ExperimentSpec`. The default config passes
  `prompt=None` (messages untouched).
- `cli.py` — `--system-prompt-file PATH` flag on the run command; when given,
  the runner maps `apply_system_prompt` over each task's input before the loop.

**Estimator (pure metrics, TDD, seeded determinism):**
- `metrics/reliability.py` — `pass_pow_k_bootstrap_ci(results, *, k, n_resamples,
  seed, alpha)` and `paired_pass_pow_k_diff_ci(results_a, results_b, *, k,
  n_resamples, seed, alpha)`: **cluster bootstrap by task** — resample the set of
  task ids with replacement, recompute pass^k over the resampled tasks, take
  percentile CIs. Reuses `agreement.py`'s `_percentile` and `BootstrapCI` *shape*;
  the shared percentile helper is **extracted to `metrics/bootstrap.py` only if
  the extraction is clean** (identical signature, no behavior change, both
  call-sites covered) — otherwise duplicated with a comment, never a forced
  refactor. Literature-style hand-computed test vectors pin the estimator (e.g. a
  3-task fixture where the cluster structure changes the CI vs a naive run-level
  resample — proving the task is the unit).

**Report (pure build + render, TDD; committed output):**
- `reports/validation.py` (**new, pure**) — `build_validation_report(...) ->
  ValidationReport` and `render_markdown(report) -> str`. Inputs: per-condition
  `RunResult` sequences (read from the streamed JSONL), the **tier map** (id →
  T1–T4, sourced from a committed `examples/datasets/workspace_tool_use_v2_tiers.json`
  generated from `review-ledger.md` — tier is **not** in the frozen task schema,
  and adding it would re-version the dataset per the rubric; a derived sidecar
  keeps the frozen set frozen), and the task metadata (capability, knob). Produces:
  - per-condition pass@1 + pass^3 **with cluster-bootstrap-by-task 95% CIs**;
  - failure taxonomy counts × tier × capability;
  - per-task pass/fail matrix (condition × task);
  - **deterministic-vs-flaky split** (all-3-fail = deterministic; mixed = flaky)
    per condition — the v1 finding was deterministic over-calling, so this split
    is the headline reliability lens;
  - exemplar trace excerpts for the top failure modes (drawn from the streamed
    JSONL trajectories, truncated);
  - per-tier accuracy curves (pass^3 by tier per condition);
  - the **discriminativeness verdict**: did v2 separate the hosted frontier
    models that v1 saturated at pass^3 = 1.000? (computed: is there ≥1 task where
    the hosted conditions' pass^3 differ, and is any hosted pass^3 < 1.000?).
- `reports/comparison.py` (**new, pure**) — `build_comparison_report(...)` /
  `render_markdown(...)`: the two-config comparison above, emitting the frozen
  hypothesis, per-config + per-tier pass^3, the Δ CI, the secondary metrics, and
  the mechanically-read verdict.

**CLI surface (decouple expensive runs from cheap reports):**
- `run-baseline` — **unchanged interface** except the two additive flags
  (`--system-prompt-file`, and per-task `max_steps` now honored). Used to produce
  each condition's `runs-*.jsonl` (the live, token-spending step).
- `report-validation` (**new**) — pure: reads the committed/streamed
  `runs-*.jsonl` for the listed conditions + the tier sidecar, writes the
  failure-mode report. Re-runnable for free (no provider calls) so the report can
  be regenerated without re-spending tokens.
- `compare-configs` (**new**) — pure: reads the two config runs' JSONL, writes the
  comparison report.
- Rationale for the split: live runs are slow and cost money; report building is
  pure and instant. Separating them means a report bug is a free re-run, and the
  expensive trajectories are captured once and reused — the same separation
  `run-baseline` already embodies (run → JSONL → pure report).

## What is committed vs gitignored

- **Committed under `docs/2026-06-10-dataset-grader-quality/`:** the **failure-mode
  report** (`failure-mode-report.md`) and the **comparison report**
  (`config-comparison.md`) — the deliverables the user reviews. `reports/` is
  gitignored, so the reviewable artifacts live under `docs/`.
- **Committed under `examples/datasets/`:** the derived tier sidecar
  (`workspace_tool_use_v2_tiers.json`) and the frozen `planning` system-prompt
  fixture (so the comparison is reproducible).
- **Gitignored (stays in `reports/`):** the raw `runs-*.jsonl` provider traces
  (large, contain full trajectories) — referenced by relative path from the
  committed reports, not inlined wholesale (only truncated exemplar excerpts are
  inlined).

## Open questions resolved (with rationale)

1. **Per-task `max_steps` vs CLI `--max-steps` precedence.** *Resolved:*
   per-task `metadata.max_steps` **wins** for that task; `--max-steps` is the
   **default for tasks without one** (a fallback floor, not a ceiling). *Why:*
   ADR-0004 is explicit that the per-task budget exists precisely so T3/T4 chains
   are not step-starved; making the CLI flag a *cap* would let a low global
   silently truncate long chains into `step_limit_exceeded` failures — the
   agent-vs-harness confound the conformance floor was built to prevent. A *high*
   global as the only knob (the rejected ADR option) would let over-calling
   models wander on short tasks, masking the `extra_call` signal. Per-task-wins is
   the only choice consistent with the ADR and the failure taxonomy.

2. **Conditions for live validation.** *Resolved:* C1–C4 above; openrouter OUT.
   *Why:* all three hosted keys are present in `.env` and the MLX server is
   confirmed up; openrouter is environmentally blocked (SKIPPED.md) and would
   fabricate a gap if forced. Four conditions span the frontier-vs-weak contrast
   that v1 established, so v2's discriminativeness is measured against the same
   field.

3. **Which two configurations to compare.** *Resolved:* same model
   (`deepseek-v4-pro`), `default` vs `planning` system prompt. *Why:* it is the
   only candidate that is genuinely an *agent-configuration* contrast (model and
   dataset held fixed), does not duplicate the multi-condition validation
   (candidate c), and does not mutate the frozen dataset (candidate b would). It
   also targets the exact mechanism v1 surfaced (over-calling on multi-step),
   making the hypothesis falsifiable and mechanistically grounded.

4. **How the runner supports a system-prompt config.** *Resolved:* a pure
   `apply_system_prompt` transform + a `--system-prompt-file` CLI flag; no
   `Condition` class, no `ExperimentSpec`. *Why:* tasks already carry their system
   prompt as `input.messages[0]`, so the knob is a one-function pure transform on
   the message tuple. Building the Weeks 7-8 experiment machinery now would be
   premature scope; the spec explicitly scopes down while keeping the statistics
   honest (the comparison still gets a pre-declared hypothesis, paired estimator,
   and CI).

5. **Estimator and resampling unit.** *Resolved:* cluster bootstrap **by task**
   for every CI (per-condition pass^3 and the paired Δ). *Why:* design §4.6 — the
   k runs of one task are not independent (they share the task), so the task is
   the resampling unit; a naive run-level resample would understate the CI width.
   Seeded RNG (default seed `20260610`, matching the calibrate command) makes
   every reported interval reproducible.

6. **n=50 honesty.** *Resolved:* the report states n=50, reports CI widths
   explicitly, and on a CI-includes-0 outcome states in words that absence of a
   detectable effect is not evidence of no effect. *Why:* with near-ceiling rates
   and 50 paired tasks the interval is wide; over-claiming would be the exact
   statistical malpractice the roadmap's estimators/CI focus exists to correct.

7. **Committed vs gitignored artifacts.** *Resolved:* reports committed under
   `docs/`; raw traces stay gitignored in `reports/`; tier sidecar + prompt
   fixture committed under `examples/`. *Why:* `reports/` is gitignored, so the
   reviewable deliverables must live under `docs/`; the traces are large and
   reproducible, so only truncated exemplars are inlined.

8. **CLI surface.** *Resolved:* keep `run-baseline` (the live, token-spending
   step) + add pure `report-validation` and `compare-configs` (free re-runs over
   captured JSONL). *Why:* mirrors the existing run→JSONL→pure-report separation;
   a report bug never costs another live run.

9. **`local` model-id mismatch.** *Resolved:* run with `--model Qwen/Qwen3-8B`
   (runtime override; the plan may alternatively fix the registry default). *Why:*
   the registry default `qwen3-8b` does not match the served id; the existing
   `--model` flag resolves it without a code change, and the report condition id
   reads the corrected id.

10. **Tier as a report dimension when the schema has no tier field.** *Resolved:*
    a committed derived sidecar `workspace_tool_use_v2_tiers.json` (id → T1–T4),
    generated from `review-ledger.md`. *Why:* the rubric declares re-review under
    a new dimension a *new dataset version*, not an in-place edit; a derived
    read-only sidecar keeps the frozen set frozen while giving the report its tier
    axis.

## Acceptance criteria (each independently verifiable)

1. **ADR-0004 honored.** `effective_max_steps(task, default)` exists in
   `runners/multi_run.py`, is pure, returns `task.metadata.max_steps` when present
   else `default`, and is threaded into `run_single`; a unit test proves a task
   with `max_steps=6` runs 6 loop iterations even when the CLI default is 4, and a
   task with `max_steps=None` falls back to the default. (Verify: pytest.)
2. **No silent step-starvation in the live runs.** After the live validation, **no
   T3/T4 task on any reachable condition fails with `step_limit_exceeded` caused by
   the budget being below its declared `max_steps`** — i.e. every task ran with at
   least its declared budget. (Verify: the failure-mode report's
   `step_limit_exceeded` count is attributable to genuine over-stepping, and the
   report asserts every task's effective budget ≥ its declared `max_steps`.)
3. **System-prompt knob works and is pure.** `apply_system_prompt(messages,
   prompt)` returns a new tuple with the system turn replaced (or prepended),
   never mutates its input, and is covered by unit tests (replace-existing,
   prepend-when-absent, `None`→unchanged). The `--system-prompt-file` flag wires it
   into `run-baseline`. (Verify: pytest + a CLI test.)
4. **Cluster-bootstrap estimator is correct and deterministic.**
   `pass_pow_k_bootstrap_ci` and `paired_pass_pow_k_diff_ci` resample **by task**,
   are seeded (same seed → identical CI), and pass literature-style hand-computed
   test vectors including one that distinguishes cluster-by-task from naive
   run-level resampling. (Verify: pytest.)
5. **Live validation ran across all reachable conditions at k=3.** A
   `runs-<slug>.jsonl` exists for each reachable condition (C1–C4), each with
   exactly 50 tasks × 3 runs = 150 run records (or a documented `blocked` status
   with reason for any unreachable condition). (Verify: line counts + the report's
   per-condition run tallies.)
6. **Failure-mode report committed and answers the headline question.**
   `docs/2026-06-10-dataset-grader-quality/failure-mode-report.md` exists and
   contains: per-condition pass@1 + pass^3 **with bootstrap CIs**; failure
   taxonomy × tier × capability; the per-task pass/fail matrix; the
   deterministic-vs-flaky split; ≥1 exemplar trace excerpt per top failure mode;
   per-tier accuracy curves; and an explicit **discriminativeness verdict** (did
   v2 separate the hosted models v1 saturated?). (Verify: read the file; the
   verdict is stated and backed by the per-condition numbers.)
7. **Two-config comparison committed and pre-declared.**
   `docs/2026-06-10-dataset-grader-quality/config-comparison.md` exists and
   contains the frozen hypothesis, the held-fixed factors, both configs' pass^3
   (overall + per-tier), the **paired Δ pass^3 with a cluster-bootstrap CI**, the
   secondary metrics (pass@1, `extra_call`/`wrong_args` rates, cost), and a verdict
   **read mechanically off the Δ (T3+T4) CI** per the frozen decision rule. The
   hypothesis text in the report matches this spec (no post-hoc editing). (Verify:
   read the file against §"The two-configuration comparison".)
8. **n=50 stated honestly.** Both reports state n=50 and report CI widths; the
   comparison, on a CI-includes-0 outcome, states that absence of a detectable
   effect is not evidence of no effect. (Verify: read.)
9. **Report tooling is pure and CLI-driven.** `reports/validation.py` and
   `reports/comparison.py` are pure (build + render, no I/O); `report-validation`
   and `compare-configs` CLI subcommands read JSONL and write Markdown; both are
   re-runnable with no provider calls. (Verify: pytest covers the pure builders;
   a CLI test runs each over a tiny fixture JSONL and asserts the rendered output.)
10. **No fabrication on failure.** A condition that is unreachable at run time is
    marked `blocked` with its reason in the report (like v1's openrouter); no
    numbers are invented for it; per-run provider errors are recorded in the
    streamed JSONL. (Verify: the report's blocked-condition handling + a unit test
    that the builder renders a `blocked` condition without inventing pass rates.)
11. **All harness gates green.** `pytest`, `ruff check`, and `ruff format --check`
    all pass on the full repo. (Verify: run them.)

## Non-goals (explicit scope-down)

- **No `ExperimentSpec` machinery** (Weeks 7-8): no declarative experiment
  objects, no dev/held-out split enforcement in this item, no multiple-testing
  control (Holm/Bonferroni). The comparison is a single pre-declared contrast, so
  multiple-testing control is not yet needed; it is named here so a later item
  adds it deliberately.
- **No judge in the v2 grading path.** Item 003's `llm_judge` grader is *not*
  exercised on the v2 set; v2 grades deterministically (`tool_call_match` /
  `final_state` / `all_of`). Calibration stays provisional per item 003.
- **No new tasks, no edits to the frozen `workspace_tool_use_v2.jsonl`.** Tier
  data is a derived read-only sidecar, not a schema change.
- **No new provider in the registry, no proxy work.** openrouter stays OUT
  (environmental, SKIPPED.md); no residential-proxy attempt.
- **No more than two configurations in the comparison.** The roadmap says "two";
  a third config (e.g. a different model) is out — it would be the multi-condition
  validation, already covered.
- **No multi-turn / `ask_user` tasks** (Weeks 9-10, SKIPPED.md).

## Constraints

- **TDD throughout:** every new pure function (estimator, `apply_system_prompt`,
  report builders) is written test-first; the live-run code is the thin edge.
- **Purity boundary:** report builders and the estimator are pure (no I/O,
  no mutation, no logging); all provider calls and file writes stay in `cli.py`
  edges. Bootstrap RNG seed is an explicit argument (default `20260610`).
- **Immutability:** `apply_system_prompt` and all builders return new values via
  spread/rebuild; no argument mutation.
- **Determinism of reports:** given the same JSONL inputs, seed, and tier sidecar,
  both reports render byte-identically (enables a regeneration check).
- **Streaming survival:** live runs stream per-task JSONL (existing behavior) so a
  mid-run provider failure never loses completed work; the local condition relies
  on this because it runs longest.
- **Cost ceiling:** hosted ≈ 150 runs/condition × ~8 calls/task; illustratively
  ~$1–2 per hosted condition (cents-to-low-dollars), plus ~300 runs for the
  deepseek two-config comparison. Acceptable. Local is free (wall-clock only).
  No condition is run more than k=3.
- **Secrets:** keys read by env-var *name* from the existing config; never logged,
  never passed as positional args.
- **Stay on branch `autodev/dataset-grader-quality-feature`; commit only the spec
  file in this step; do not push.**
