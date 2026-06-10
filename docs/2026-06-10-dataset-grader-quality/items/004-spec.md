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

**The planning prompt is itself a measured artifact — it must be hash-pinned
(Resolved Q5).** The comparison is unreproducible if the prompt text can drift.
So the committed fixture's bytes are pinned by a **sha256 over its
canonical-bytes rendering**, recorded in the comparison report's header,
**reusing the existing `graders/judge.prompt_hash` + `graders/canonical`
precedent** (the CONTEXT.md *prompt hash* term — the same sha256-over-canonical
pattern item 003 uses for judge prompts). Configuration A has *no* single prompt
to hash (each task carries its own author prompt in `input.messages[0]`), so the
report records A as `"per-task author prompt (no override)"` and pins **B's**
fixture hash — the one varying, controllable input.

- **Held fixed:** model = `deepseek:deepseek-v4-pro` (the cheapest reliable
  hosted frontier model; one model keeps the comparison a clean agent-config
  contrast and the token spend bounded), dataset = `workspace_tool_use_v2`
  (all 50 tasks, paired), k=3, ~~temperature=0.0~~ **temperature=0.0 *requested*
  (Resolved Q10)**, per-task `max_steps`, registry = `WORKSPACE_TOOLS`.
  - **Temperature/seed honesty (Resolved Q10):** `runners/client.py` *does* send
    `temperature` in the request body (CLI default `0.0`), so "temp=0.0" is an
    honest claim — but it sends **no seed** (the OpenAI-compatible body has none)
    and hosted providers are **not greedy-deterministic at temp 0**. The report
    therefore states temperature=0.0 was *requested* and that residual run-to-run
    variation is exactly what k=3 + pass^3 measures — it never claims bit-exact
    determinism the harness does not control. The only seeded, reproducible knob
    is the bootstrap RNG.
  - **The two configs share `condition_id = "deepseek:deepseek-v4-pro"` (Resolved
    Q11):** `condition_id` is `provider:model` and is stamped *inside* every
    `RunResult` (`serialize.run_result_to_dict`), so the two configs are
    indistinguishable by the in-record id — they are distinguished only by their
    **source artifact** (`…__default.jsonl` vs `…__planning.jsonl`).
    `compare-configs` therefore takes the **two JSONL paths as explicit `A` / `B`
    arguments** and labels them by *config role*, never by the in-record
    `condition_id`. Re-stamping a synthetic per-config id into the records is a
    rejected alternative (it would mutate the v1 `RunResult` schema; the
    path-as-identity choice keeps the record schema frozen — see ADR-0007).

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

- **Primary metric:** ~~**pass^3 on the paired 50 tasks**~~ **the paired
  difference Δ = pass^3(B) − pass^3(A) on the hard tiers (T3+T4)** — *see Resolved
  decision Q3*: the hypothesis is directional and tier-scoped (planning helps on
  hard tiers, T1+T2 indistinguishable), and the decision rule below is read off
  the **T3+T4** CI, so the T3+T4 Δ is the *primary* metric, not the overall-50 Δ.
  Reported per configuration and as the paired difference with a
  **cluster-bootstrap-by-task 95% CI** on Δ (resample the *task ids* with
  replacement; both configs' k=3 outcomes for a resampled task move together —
  the pairing is preserved within a resampled task; the overall-50 Δ is a
  **secondary** descriptive number, not the verdict input).
  - **Pairing is an enforced precondition, not a hope (Resolved Q1):**
    `paired_pass_pow_k_diff_ci(results_a, results_b, …)` **requires the two
    sequences cover the identical task-id universe** and raises on mismatch — a
    blocked or short condition can never be silently half-paired. Each bootstrap
    iteration draws **one** task-id multiset and applies it to *both* configs, so
    the within-task pairing is structural. Seeded RNG (`seed=20260610`, matching
    `calibrate`/`agreement.py`) ⇒ byte-identical CI on re-run. There is **no
    `1-p_e`-style degeneracy class for pass^k** (unlike Cohen's κ, ADR-0006); a
    resample drawing an all-pass or all-fail task multiset yields a legitimate
    pass^k of 1.0/0.0, so the `BootstrapCI` shape is reused but its
    `n_degenerate` field is always 0 (or omitted) — *not* copied blindly from the
    κ path (Resolved Q2).

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
  wall-clock-dominant: 50 tasks × 3 runs × ~~up-to-6-step~~ **up-to-6-loop-step
  (the declared v2 `max_steps` ceiling is 6, not the 8–10 the earlier prose
  implied — Resolved Q8)** chains on an 8B MLX model may run long — acceptable
  because it is free and the harness streams per task, so a mid-run failure never
  loses completed work).
  - **Partial-condition recovery (Resolved Q8):** because runs stream per task to
    JSONL, an interrupted local condition leaves a *partial* `runs-*.jsonl` (fewer
    than 50×3 records). The report builders **accept a partial condition and mark
    it `incomplete` with its actual run tally** rather than blocking the whole
    deliverable; `report-validation` can be re-run for free as more records land.
    Only a condition with **zero** reachable records is `blocked` (AC 10). The
    plan owns the per-condition progress story (the streamed JSONL *is* the
    progress log; tail it for `task_id` count). Each condition writes its own
  `runs-<condition-slug>.jsonl` (per-condition artifact naming, commit c744b5f).
  **The two-config comparison reuses the same `deepseek:deepseek-v4-pro` model,
  so its two runs would both slug to `runs-deepseek-deepseek-v4-pro.jsonl` and
  collide — the *exact* cross-model-overwrite bug class the repo already fixed in
  c744b5f (CHANGELOG `Fixed`). Resolved Q11 (ADR-0007): the artifact slug extends
  with an optional prompt-config tag** (`runs-deepseek-deepseek-v4-pro__default.jsonl`
  / `…__planning.jsonl`); when no `--system-prompt-file` is given the tag is empty
  and the filename is **byte-for-byte the v1 name** — so all 20 v1 tasks, every
  hosted/local validation condition, and the existing
  `test_artifacts_are_distinct_per_model_under_one_provider` guard stay unchanged.
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
  percentile CIs. **The paired form takes one task-id multiset per iteration and
  applies it to both configs so within-task pairing is structural, and it raises
  if `results_a`/`results_b` do not cover the identical task-id universe (no
  silent half-pairing — Resolved Q1).** Reuses `agreement.py`'s `_percentile` and
  `BootstrapCI` *shape* (but pass^k has **no `1-p_e` degeneracy class** —
  `n_degenerate` ≡ 0, Resolved Q2);
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
  - the **discriminativeness verdict** (mechanically pre-defined, Resolved Q9 —
    *not* read off vibes): did v2 separate the hosted frontier models that v1
    saturated at pass^3 = 1.000? Two mechanical rungs, both computed, both
    reported:
    - **Strong (the headline claim):** ≥1 *pair* of hosted conditions is
      separated by a **pass^3 gap whose paired cluster-bootstrap-by-task CI
      excludes 0** (reusing `paired_pass_pow_k_diff_ci` across the two hosted
      conditions, on the same 50 paired tasks) — *and/or* the per-tier pass^3 is
      **monotone non-increasing T1≥T2≥T3≥T4** for ≥1 hosted condition (a genuine
      capability gradient, not a flat ceiling).
    - **Weak (necessary, not sufficient):** ≥1 task where the hosted conditions'
      pass^3 differ **and** ≥1 hosted pass^3 < 1.000 (v1 had neither — all hosted
      saturated at 1.000).
    The verdict states which rung is met. "v2 discriminates" is claimed **only**
    on the strong rung; the weak rung alone is reported as "v2 is no longer
    saturated, but the separation is within noise at n=50" (the same n=50 honesty
    the comparison applies).
- `reports/comparison.py` (**new, pure**) — `build_comparison_report(...)` /
  `render_markdown(...)`: the two-config comparison above, emitting the frozen
  hypothesis, per-config + per-tier pass^3, the Δ CI, the secondary metrics, and
  the mechanically-read verdict.

**CLI surface (decouple expensive runs from cheap reports):**
- `run-baseline` — **unchanged interface** except the two additive flags
  (`--system-prompt-file`, and per-task `max_steps` now honored). Used to produce
  each condition's `runs-*.jsonl` (the live, token-spending step). When
  `--system-prompt-file` is given, the artifact slug gains the **prompt-config
  tag** (`…__<tag>.jsonl`, tag derived from the fixture stem); absent the flag the
  filename is byte-identical to v1 (Resolved Q11 / ADR-0007).
- `report-validation` (**new**) — pure: reads the committed/streamed
  `runs-*.jsonl` for the listed conditions + the tier sidecar, writes the
  failure-mode report. Re-runnable for free (no provider calls) so the report can
  be regenerated without re-spending tokens.
- `compare-configs` (**new**) — pure: takes the **two config JSONL paths as
  explicit `--config-a` / `--config-b` arguments** (the two configs share the
  in-record `condition_id`, so the *source path*, labeled by config role, is the
  identity — Resolved Q11), writes the comparison report.
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
2. **No silent step-starvation in the live runs.** After the live validation,
   **every task ran with at least its declared `metadata.max_steps` budget** (the
   effective budget ≥ declared for all 50 tasks on every reachable condition).
   ~~the failure-mode report's `step_limit_exceeded` count is attributable to
   genuine over-stepping~~ **Resolved Q7 — the starvation signature is corrected:**
   `runners/loop.py` initializes `stop_reason="max_steps"` and a chain that
   exhausts the loop without a final `MessageTurn` keeps that stop reason, but
   **`stop_reason="max_steps"` is *not* a `FailureCategory`** — the grader's
   `step_limit_exceeded` is emitted **only** by an explicit `MaxToolCalls`
   constraint breach (`graders/policy.py`). A *starved* chain therefore fails its
   `FinalStateSpec` **outcome** with `failure_reason=None` (a missed expectation),
   *not* `step_limit_exceeded`. So the report asserts the budget floor directly
   (every effective budget ≥ declared) **and** cross-checks that no
   `stop_reason="max_steps"` trajectory on a reachable condition coincides with an
   effective budget below that task's declared `max_steps`. (The declared maximum
   across v2 is **6** — equal to today's CLI default — so wiring's live effect is
   chiefly to stop *over*-budgeting the 20 `max_steps:4` tasks that would
   otherwise run at 6 and let an over-caller wander; see Resolved Q7.) (Verify:
   the report's budget-floor assertion + the loop-semantics note.)
3. **System-prompt knob works and is pure.** `apply_system_prompt(messages,
   prompt)` returns a new tuple with the system turn replaced (or prepended),
   never mutates its input, and is covered by unit tests (replace-existing,
   prepend-when-absent, `None`→unchanged). The `--system-prompt-file` flag wires it
   into `run-baseline`. (Verify: pytest + a CLI test.)
4. **Cluster-bootstrap estimator is correct and deterministic.**
   `pass_pow_k_bootstrap_ci` and `paired_pass_pow_k_diff_ci` resample **by task**
   (one task-id multiset per iteration), are seeded (same seed → identical CI),
   and pass literature-style hand-computed test vectors including one that
   distinguishes cluster-by-task from naive run-level resampling. **The paired
   estimator enforces an identical task-id universe across its two inputs and
   raises on mismatch (Resolved Q1); a unit test pins the raise.** There is no
   `1-p_e`-style degeneracy class for pass^k, so `n_degenerate` is always 0 /
   omitted (Resolved Q2) — a test asserts an all-pass and an all-fail resample
   both yield legitimate finite CIs, not a degenerate flag. (Verify: pytest.)
5. **Live validation ran across all reachable conditions at k=3.** A
   `runs-<slug>.jsonl` exists for each reachable condition (C1–C4); a *complete*
   condition has exactly 50 tasks × 3 runs = 150 run records. A condition with
   **some but not all** records is reported `incomplete` with its actual tally
   (Resolved Q8 — partial-condition handling, not blocking); a condition with
   **zero** reachable records is `blocked` with its reason (AC 10). Numbers are
   computed only over the records that exist; none are invented. (Verify: line
   counts + the report's per-condition run tallies and per-condition status.)
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
10. **No fabrication on failure; incomplete ≠ blocked.** A condition unreachable
    at run time (zero records) is marked `blocked` with its reason (like v1's
    openrouter); a condition with a *partial* record set is marked `incomplete`
    with its actual tally and graded only over the records present (Resolved Q8);
    **no numbers are invented for either**; per-run provider errors are recorded
    in the streamed JSONL. (Verify: the report's blocked/incomplete handling + a
    unit test that the builder renders a `blocked` condition and an `incomplete`
    condition without inventing pass rates.)
11. **Two-config artifacts never collide; v1 naming preserved.** The two
    same-model configs write to distinct files via the prompt-config tag
    (`…__default.jsonl` / `…__planning.jsonl`), and `compare-configs` identifies
    them by **source path**, not by the shared in-record `condition_id` (Resolved
    Q11 / ADR-0007). With no `--system-prompt-file`, the artifact filename is
    byte-identical to v1 and `test_artifacts_are_distinct_per_model_under_one_provider`
    stays green. (Verify: a CLI test that two same-model configs produce two files
    and the existing no-tag artifact name is unchanged.)
12. **All harness gates green.** `pytest`, `ruff check`, and `ruff format --check`
    all pass on the full repo. (Verify: run them.)

## Non-goals (explicit scope-down)

- **No `ExperimentSpec` machinery** (Weeks 7-8, design §4.6/§7): no declarative
  experiment objects, no `MetricDef`/`Condition`/`DecisionRule`/`spec_hash`
  records, no dev/held-out split enforcement, no multiple-testing control
  (Holm/Bonferroni). **The verdict reads exactly *one* pre-declared CI — the
  T3+T4 Δ pass^3 interval — so there is no family of comparisons and no
  family-wise error to correct** (the discriminativeness rungs are *descriptive*
  reporting, not a second hypothesis test driving the verdict). The hash-pinning
  here (the planning-prompt fixture sha256) is the *poor-man's* `spec_hash` — it
  pins the one varying input for reproducibility without building the Weeks-7-8
  pre-registration object. Multiple-testing control is named here so a later item
  adds it deliberately when E2's pairwise model matrix lands.
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

## Resolved decisions

Output of the `grill-with-docs` pass (subagent: opus) hardening this spec against
the domain model *before* the plan phase. Autonomy override in effect: each
question is auto-resolved to the reviewer's recommended answer. Corrections are
applied as inline strike-throughs above; nothing is deleted.

**Q1 — Is the pairing pinned (bootstrap resamples *tasks*; both configs' runs for
a sampled task move together)?** The spec's prose said so, but the
`paired_pass_pow_k_diff_ci(results_a, results_b, …)` signature took two separate
sequences with the pairing invariant only narrated.
- **A:** Pin it as an **enforced precondition**: the paired estimator requires
  `results_a` and `results_b` to cover the **identical task-id universe** and
  **raises on mismatch** (a blocked/short condition can never be silently
  half-paired); each bootstrap iteration draws **one** task-id multiset and
  applies it to *both* configs, so within-task pairing is structural. A unit test
  pins the raise.
- **Rationale:** design §4.6 is binding — "conditions are compared on the **same
  paired tasks**". Narrated pairing is not enforced pairing; a function that
  accepts mismatched universes will eventually be handed one.
- **Doc impact:** spec Primary-metric block, Architecture estimator bullet, AC 4.

**Q2 — Degenerate-resample policy vs `agreement.py`'s D7 precedent.** κ has a
`1-p_e==0` degenerate path counted in `n_degenerate` (D7); does pass^k need the
same?
- **A:** **No.** pass^k has **no `1-p_e`-style degeneracy class** — an all-pass or
  all-fail resampled task multiset yields a *legitimate* pass^k of 1.0/0.0. The
  `BootstrapCI` *shape* is reused for consistency, but `n_degenerate ≡ 0` (or is
  omitted) and is **not** copied blindly from the κ path. A test asserts all-pass
  and all-fail resamples both produce finite CIs, not a degenerate flag.
- **Rationale:** copying the D7 field verbatim would imply a degeneracy that does
  not exist for this estimand — a domain-model-fidelity bug. Reuse the shape, not
  the meaning.
- **Doc impact:** spec Primary-metric block, Architecture estimator bullet, AC 4.

**Q3 — Primary-metric scope contradiction.** §"Primary metric" named "pass^3 on
the paired 50 tasks" but the decision rule reads the **T3+T4** Δ CI — two
different CIs, one of them unnamed-as-primary.
- **A:** The **primary metric is the T3+T4 Δ pass^3 CI** (where the directional,
  tier-scoped hypothesis lives); the overall-50 Δ is reported **secondary,
  descriptive**. The verdict is read off the metric the spec declares primary.
- **Rationale:** the hypothesis is explicitly "planning helps on hard tiers,
  T1+T2 indistinguishable". Reading the verdict off a CI the spec called primary
  but the hypothesis never targeted is exactly the kind of estimand slippage the
  pre-registration discipline exists to prevent.
- **Doc impact:** spec Primary-metric block (strike-through), AC 7 already keyed
  to the T3+T4 CI (consistent).

**Q4 — Seeding.** *Resolved:* bootstrap RNG default seed `20260610`, matching
`calibrate`/`agreement.py`, an explicit argument; same seed ⇒ byte-identical CI.
No ADR (matches the established precedent). **Doc impact:** Primary-metric block,
Constraints.

**Q5 — The planning system prompt is a measured artifact; where is it pinned?**
Without a content pin the comparison is unreproducible (the prompt can drift).
- **A:** Commit the prompt as a fixture under `examples/datasets/` (already
  required) **and record its sha256-over-canonical-bytes in the comparison report
  header**, reusing the existing `graders/judge.prompt_hash` + `graders/canonical`
  precedent (the CONTEXT.md *prompt hash* term). Config A has no single prompt to
  hash (per-task author prompt), so the report pins **B's** fixture hash and
  records A as "per-task author prompt (no override)".
- **Rationale:** reproducibility of a *comparison whose only varying input is a
  prompt* requires pinning that input; the project already has the exact
  sha256-over-canonical machinery item 003 uses for judge prompts — reuse it, do
  not invent a parallel hash.
- **Doc impact:** spec Configuration-B block.

**Q6 — `max_steps` loop semantics at exhaustion.** Does an exhausted chain grade
as `step_limit_exceeded`? Does per-task wiring change any v1 behavior?
- **A:** **No** — `runners/loop.py` sets `stop_reason="max_steps"` on exhaustion,
  but **`stop_reason="max_steps"` is not a `FailureCategory`**: the grader's
  `step_limit_exceeded` is emitted **only** by an explicit `MaxToolCalls` breach
  (`graders/policy.py`). A starved chain fails its `FinalStateSpec` **outcome**
  with `failure_reason=None` (a missed expectation). The starvation *signature*
  in AC 2 is corrected accordingly: assert the budget floor directly and
  cross-check `stop_reason="max_steps"` trajectories against the declared budget.
  v1 behavior is **unchanged**: all 20 v1 tasks carry **no** `max_steps`, so the
  CLI default still applies to them verbatim.
- **Rationale:** the original AC 2 conflated the loop's `stop_reason` with the
  grader's policy category — they are different layers. The declared v2 `max_steps`
  ceiling is **6** (= today's default), so wiring's live effect is chiefly to stop
  *over*-budgeting the 20 `max_steps:4` tasks (preserving the `extra_call` signal),
  not to rescue 8–10-step chains that do not exist in the set.
- **Doc impact:** spec AC 2 (strike-through + correction), Run-order block.

**Q7 — Temperature/seed honesty.** Does the client actually send temperature?
- **A:** **Yes** — `runners/client.py` always sends `temperature` (CLI default
  `0.0`), so "temp=0.0" is honest. But it sends **no seed** (none exists in the
  OpenAI-compatible body) and hosted providers are **not greedy-deterministic at
  temp 0**. The report states temperature was *requested* at 0.0, that residual
  run-to-run variation is exactly what k=3 + pass^3 measures, and never claims
  bit-exact determinism the harness does not control.
- **Rationale:** record what is actually sent; do not claim control that does not
  exist. The only seeded, reproducible knob is the bootstrap RNG.
- **Doc impact:** spec Held-fixed block (strike-through + temperature/seed note).

**Q8 — Local Qwen wall-clock + partial-condition reports.** The long local
condition could be interrupted; can the report build from partial data?
- **A:** **Yes.** Because runs stream per task, an interrupted condition leaves a
  *partial* `runs-*.jsonl`; the builders mark it `incomplete` with its actual
  tally and grade **only over present records** — never blocking the deliverable
  and never inventing the missing runs. A **zero-record** condition is `blocked`
  (distinct status). The overstated "up-to-6-step / 8–10" prose is corrected: the
  declared `max_steps` ceiling is **6 loop iterations**, so the wall-clock fear is
  bounded.
- **Rationale:** the streaming-survival property (commit 7a651bc) already captures
  completed work; the report must honor it rather than treating partial as
  failure. `incomplete ≠ blocked ≠ fabricated` is the honest three-way split.
- **Doc impact:** spec Run-order block (partial-recovery), AC 5, AC 10.

**Q9 — Discriminativeness verdict: mechanical, not vibes.** What does "v2
discriminates" mean precisely?
- **A:** Two mechanical rungs, both computed: **strong** = ≥1 hosted *pair*
  separated by a pass^3 gap whose **paired cluster-bootstrap CI excludes 0**
  and/or **per-tier monotone non-increasing T1≥T2≥T3≥T4** for ≥1 hosted condition;
  **weak** = ≥1 task where hosted pass^3 differ *and* ≥1 hosted pass^3 < 1.000.
  "v2 discriminates" is claimed **only** on the strong rung; the weak rung alone
  reads "no longer saturated, but within noise at n=50".
- **Rationale:** "did v2 separate the models" must be a computation, not a
  judgment call. The strong rung reuses the same paired estimator and applies the
  same n=50 honesty as the comparison.
- **Doc impact:** spec failure-mode-report discriminativeness bullet.

**Q10 / Scope — single contrast ⇒ no multiple-testing.** *Resolved:* the verdict
reads exactly **one** pre-declared CI (the T3+T4 Δ), so there is no family of
comparisons and no family-wise error; the discriminativeness rungs are
descriptive, not a second verdict-driving test. The prompt-fixture sha256 is the
*poor-man's* `spec_hash` — pinning the one varying input without the Weeks-7-8
pre-registration object. **Doc impact:** spec Non-goals (sharpened). No ADR (a
restatement of existing scope, not a reversible trade-off).

**Q11 — Condition-naming collision: two configs of one model overwrite each
other.** `condition_id` is `provider:model` and is stamped *inside* every
`RunResult`, so the `default` and `planning` runs of `deepseek:deepseek-v4-pro`
both slug to `runs-deepseek-deepseek-v4-pro.jsonl` **and** carry an identical
in-record `condition_id` — the **exact cross-model-overwrite bug class the repo
already fixed once** (commit c744b5f, CHANGELOG `Fixed`; guarded by
`test_artifacts_are_distinct_per_model_under_one_provider`).
- **A:** **Extend the artifact slug with an optional prompt-config tag**
  (`…__default.jsonl` / `…__planning.jsonl`), empty when no `--system-prompt-file`
  is given (so the v1 filename and the existing guard are byte-for-byte
  unchanged). `compare-configs` identifies the two configs by **source path,
  labeled by config role**, *not* by the shared in-record `condition_id`. The
  `RunResult` record schema is **not** mutated (rejected alternative: re-stamping
  a synthetic per-config id into every record).
- **Rationale:** ADR-worthy (three-of-three) — *hard to reverse* once artifacts
  and any tooling that parses their names exist; *surprising* (a reader expects
  `condition_id` to be the run identity, but here two distinct runs share it);
  *real trade-off* (filename-tag vs record-schema-change vs synthetic-id). Picking
  filename-tag keeps the frozen `RunResult` schema and the v1 artifact contract
  intact.
- **Doc impact:** **ADR-0007**; spec Run-order block, Held-fixed block, CLI-surface
  block, AC 11; CONTEXT.md adds **prompt-config tag**.
