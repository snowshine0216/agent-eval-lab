# Agent Eval Lab — Design: Per-domain round caps + F-set harness-factor ablation

- **Date:** 2026-06-15
- **Status:** **Active** (brainstormed 2026-06-15; survived **three** adversarial
  pre-spec review rounds — traced in §8/§9/§10 — then a CONTEXT-grounded grilling
  pass that simplified the design and aligned it to the glossary, traced in §11).
  Glossary terms and ADRs-0016/0017 were written inline during grilling.
- **Scope:** Two coupled enhancements to the agentic-v1 eval pipeline:
  1. a **per-domain `max_rounds`** turn-bound (code → 20, browser → 50), the
     user-facing budget; `safety_cap` demoted to a backstop. Applies to **F + D**
     now; **B deferred** (no live B model loop exists yet — §9.9).
  2. an **F-only, exploratory, 2×2 harness-factor ablation** (context-gathering
     prompt nudges × a sandboxed self-verification feedback loop) over F1/F2/F3,
     plus the scoring/classifier/record corrections the ablation depends on.
- **Source:** [reports/agentic-v1/M1-F-failure-analysis.md](../../../reports/agentic-v1/M1-F-failure-analysis.md)
  and the owner's "harness lessons" table (§3).
- **Relationship to prior specs / decisions:** continues
  [2026-06-12-use-case-agentic-eval-design.md](2026-06-12-use-case-agentic-eval-design.md)
  and the F candidate-edit run in
  [docs/2026-06-13-agentic-v1-domains-runs](../../2026-06-13-agentic-v1-domains-runs).
  Touches ADR-0008/0009 (effect-requests / **frozen** canonical output — §9.7),
  ADR-0013 (classifier versioning → mints **fc-v4**), and D34/D35/D33/D19/D32.

---

## 1. The question this phase answers

The clean M1 F-run scored **0.000 pass^k for every model except Qwen3.6-35B**
(0.333, F3 only). The failure analysis isolates three *mechanism* classes:

1. **Missing contract depth** — edits matched the *shape* but missed the
   contract (F1: instant visibility check instead of a `waitFor*` poll/
   timeout/throw helper; F2: collapsed `result.signal`+`result.confidence`).
2. **No feedback loop** — models committed after 1–2 *blind* edits. The lone F3
   pass was Qwen3.6 iterating **13 edits / 16 rounds** — blind, by persistence.
3. **Budget runaway** — GLM ~200 rounds / 1.7M tokens on F2's 37 KB config
   before the tool-call `safety_cap` stopped it; Qwen3.5 1.3M.

The eval has no turn bound, no self-verification affordance, and no scaffolding.
This phase adds a real turn budget and asks one **exploratory** question: *do
harness-level interventions — context-gathering prompts (P), and a sandboxed
feedback loop (V) — change F outcomes, and through which mechanism?*

This is **not** a claim that the harness improves coding ability in general. The
factors were derived from the observed failures on these exact three tasks
(§8.4); confirmatory evidence is deferred to a held-out set (§F).

## 2. Domain → "code vs browser" mapping (verified)

| domain | runner | tools | class | `max_rounds` | status |
|---|---|---|---|---|---|
| **F** | `f_candidate` | code-world file edits | code | **20** (ablation: 40) | live |
| **D** | `dset_run` | `BROWSE_TOOLS` / playwright-cli | browser | **50** | live |
| **B** | `b_run` | MSTR Library UI / playwright-cli | browser | **50** | **deferred** (no model loop yet) |

## 3. The owner's "harness lessons" — where each lands

| Lesson | Folds into |
|---|---|
| Read the called method's body before asserting on its behaviour | **Factor P** |
| Read local conventions (CLAUDE.md/README/config) first | **Factor P** |
| Read sibling methods before adding one | **Factor P** |
| Read the full suite, not just the failing test | **Factor P** |
| File-redirect instead of pipe (don't truncate test output mid-stream) | **Harness quality** — tail-aware feedback rendering (§B.4), *not* a global change to the frozen oracle canonicalizer (§9.7) |

---

## PART A — Per-domain `max_rounds` (F + D now; B deferred)

### A.1 Problem
The loop's only runaway bound is `safety_cap` on **total tool calls**
([loop.py:178](../../../src/agent_eval_lab/runners/loop.py:178)). `rounds` is
recorded but never bounded. The classifier's budget override keys on
`stop_reason == "max_steps"` — a literal the loop **never emits** (it emits
`safety_cap`), so that override is currently **dead code**.

### A.2 Change
- `run_single` gains `max_rounds: int | None` (default `None` ⇒ unchanged).
  Checked at the **end** of each iteration (after the round's tool calls apply,
  so the turn's work is kept), beside the `safety_cap` check:
  ```python
  if max_rounds is not None and rounds >= max_rounds:
      stop_reason = "max_rounds"; max_rounds_bound = True; break
  ```
  Natural completion breaks earlier (`completed_natural`), so a `max_rounds`
  stop means the model was **still editing** at the cap — uncommitted/incomplete.
- **Record the configured policy on the trajectory (§9.2):** `Trajectory` gains
  `max_rounds: int | None`, `safety_cap: int | None`, and `max_rounds_bound:
  bool` — so any artifact proves whether it ran at 20 or 40. `serialize.py`
  round-trips all three (defaults for old records).
- New `stop_reason` literal `"max_rounds"`.
- **Config + granularity (ADR-0017, §11.3):** per-domain default
  `max_rounds = {"F": 20, "D": 50}` on the experiment spec, with an optional
  per-task `metadata.max_rounds` override (the `rounds`-flavored successor to the
  per-task `metadata.max_steps` hint; resolution: task override > domain default).
  `safety_cap` stays a higher backstop (code 200 / browser ~300). Threaded into
  `make_f_run_fn` and `dset_run`. **B is config-only/deferred** until the live B
  runner exists (§9.9). The runner-level `max_steps` argument is **superseded**
  (ADR-0017); the `metadata.max_steps` data field is untouched.

### A.3 `max_rounds` primary, `safety_cap` backstop
`max_rounds` counts model turns (what "round" means, what the owner specified);
`safety_cap` counts tool calls and only catches a turn emitting many parallel
calls.

---

## PART B — F-set harness-factor ablation (F-only, exploratory)

### B.1 Factorial
Two independent binary factors → four **arms** (glossary term, §11.1); each
(base-task × arm) is a **distinct `task_id`** — `f-f1-bare`, `f-f1-prompt`,
`f-f1-feedback`, `f-f1-both` (and f2/f3), all sharing that base task's held-out
`VerificationSpec`. So the F-ablation set is **12 task-arms** (3 × 4).

| arm | task_id suffix | Factor P | Factor V |
|---|---|---|---|
| `bare` | `-bare` | — | — |
| `prompt` | `-prompt` | ✓ | — |
| `feedback` | `-feedback` | — | ✓ |
| `both` | `-both` | ✓ | ✓ |

**Uniform 40-round cap** across all four arms (production F stays 20) so a
feedback "win" cannot be confounded with extra budget (§8.3). The 40-round
policy is frozen in a **separate** `experiments/f_ablation_spec.py` (§9.2),
distinct from production `m1_spec`.

### B.2 Arm identity — arm-as-task (§11.1; **retires** §9.3 / §10.1 / §10.2 / §10.5)
An **arm is a distinct `task_id`** — the M2 pattern (`b-b1-noskill`/`b-b1-skill`,
[b_tasks.py:67](../../../src/agent_eval_lab/datasets/b_tasks.py:67)): same held-out
`VerificationSpec`, config differing only in injected prompt and/or tools. It is
**not** a new record field and **not** part of `condition_id`. This is the single
biggest simplification from the grilling pass — because the arm rides `task_id`
(already on `RunResult`, already in `serialize`, already the `pass_pow_k` grouping
key), three round-3 findings *evaporate*:

- **#10.1 (report join):** arms are different `task_id`s, so `pass^k` (computed
  per task) separates them for free — no `(condition_id, arm_id)` re-key, no
  `--runs` arm slot, no last-write-wins collapse.
- **#10.2 (spec_hash):** nothing touches `ConditionDef`/`ExperimentSpec`, so the
  committed frozen M1 specs keep verifying. **No `ArmDef`, no `tool_set_hash`
  field.**
- **#10.5 / #9.3 (serialize + filename + pricing):** no `arm_id` field;
  `condition_id` stays `provider:model` so `prices[condition_id]` resolves; one
  artifact per condition holds all 12 task-arms (no per-arm filename).

Mechanics:
- **Factor P** rides the task's system `messages` (the prompt block appended to
  `_EDIT_SYSTEM`); **Factor V** rides the task's `available_tools` (adds the
  V-specific `run_tests`) + the executor the **`world binding`** resolves from it.
- The four arm-tasks of one base task share **byte-identical
  `initial_state.files`** (the enriched tree, §B.5) and the **same
  `verification`**; they differ *only* in `messages` (P) and
  `available_tools`+executor (V).
- **`run_uid` becomes task-scoped** (`{condition_id}__{task_id}__{run_index}`,
  glossary) — required now that 12 task-arms share a condition's run space.
- **Artifact:** one `runs-ablation-{slug}-F.jsonl` per condition; `report-m1`'s
  `_load_run_results` already groups by `task_id`, so per-arm `pass^k` falls out
  with no report-side plumbing.

### B.3 Factor P — context-gathering prompt nudges
A discrete, attributable block appended to `_EDIT_SYSTEM`
([f_candidate.py:51](../../../src/agent_eval_lab/runners/f_candidate.py:51)):
read the **body of the method a call/assertion depends on**; read **sibling
methods** before adding one; read **local conventions**; read the **full target
file + full visible test set** before the first edit; **change only what the
task requires**. ("visible tests", not "public" — glossary term, §11.4.)

**These directives only mean something if the referenced context is present.**
F1/F2 candidate trees today contain *only* `target_paths` + a minimal
`package.json` ([f_run.py:35](../../../src/agent_eval_lab/runners/f_run.py:35));
only F3 gets a broader layer. So P is currently vacuous/failed-read pressure for
F1/F2 (§9.4). **Required fix (§B.5).**

### B.4 Factor V — confined self-verification feedback loop
V arms get a V-specific `run_tests` tool that runs the model's own **authored
tests** (glossary, §11.4) under **confined execution** (glossary + ADR-0016) —
never the seeded visible tests, never the oracle.

- **Process isolation = confined execution (§9.1 + §10.3 + ADR-0016 — P0):** the
  V executor wraps `node --test` in a macOS **`sandbox-exec` seatbelt** profile
  that is **deny-read-by-default
  with an explicit read-allowlist** — only the candidate temp tree + the node
  install dir + the enumerated system paths node needs to start (`/usr/lib`,
  `/System`, the dyld shared cache, and the `/usr/bin:/bin:<node parent>` of
  `_node_env`, [node_edge.py:85](../../../src/agent_eval_lab/runners/node_edge.py:85))
  — plus **`(deny network*)`** and **`(deny file-write*)` outside the tree**.
  A read-**allowlist** is mandatory, not a convenience: a *broad* `(allow
  file-read*)` would let model JS read `evaluator-only/` and **print the golden
  to stdout, which is returned to the model in-trajectory** — `deny network*`
  alone does NOT close that channel. New module
  `runners/sandboxed_node_edge.py`; the **trusted oracle keeps its un-sandboxed
  `node_edge` path** (evaluator code; leaving it untouched preserves its frozen
  records — §9.7). **Risk:** the allowlist is brittle across node/macOS versions;
  if it cannot be made to both start node and block an `evaluator-only/` read,
  **escalate to Docker `--network none`** (only the temp tree mounted) — the
  read-confinement is hermetic there. The macOS-only gate means V **does not run
  on Linux CI**; CI uses the injected fake executor and the ablation is declared
  **macOS-local-only**, so a CI skip cannot silently void or bias results.
- **Platform gate:** seatbelt is macOS-only. The sandboxed executor probes
  Darwin + `sandbox-exec` availability (à la `node_supports_junit`); on a
  non-macOS host (CI), real V execution **skips** and unit tests inject a fake
  executor (the executor is already an injected callable). V runs are
  macOS-local-only by design; this is recorded in the ablation spec.
- **Provenance + tool definition (§10.8):** V arms get a **V-specific
  `run_tests` ToolDef** with a node-accurate description (today's reads "Run
  pytest over every visible test", [code_world.py:83](../../../src/agent_eval_lab/tools/code_world.py:83)
  — wrong and misleading for the node path). The `ExecutionRequest` carries only
  `files` and `_run_tests` snapshots the **whole** tree
  ([code_world.py:243](../../../src/agent_eval_lab/tools/code_world.py:243)), so
  `make_authored_test_executor` itself runs **only** `tests/authored/`
  (reserved writable path no seeded tree populates) regardless of request
  contents — F3's seeded causal tests are *not* run as feedback, and
  model-supplied commands are **rejected** (fixed `node --test tests/authored/`).
  Reserved-path scoping is for *provenance*; the seatbelt sandbox is the
  *security boundary*.
- **Output (§9.7):** the global `truncate_output` (frozen oracle contract,
  ADR-0009) is **not** changed. V feedback uses a **separate tail-aware
  rendering** (failure summaries print at the end of a node run); persisted V
  records are a **distinct versioned record class**, leaving the oracle's
  head-truncated `ExecutionResult` byte-stable.
- Reuses ADR-0008: `run_tests` → `ExecutionRequest`
  ([code_world.py:241](../../../src/agent_eval_lab/tools/code_world.py:241)) →
  `make_authored_test_executor` (sandboxed) → `ToolSuccess`. `bare`/`prompt`
  keep `executor=None` + no `run_tests`.
- Worktree-per-arm is permitted purely for **parallelism** (mounted as the
  candidate tree); it is not the security boundary.

### B.5 Candidate-tree enrichment + visible/oracle curation (§9.4 + §11.6 — required for P and V)
Per F task, define a **context set** materialized **identically across all four
arms** from the pinned base SHA (D32; m2021 never read). **Curation rule
(§11.6):** include exactly what Factor P *names* — the **sibling modules** in the
edit target's layer, the **local conventions** file if the layer has one, and the
**visible tests** that exercise the contract — and **exclude anything that reveals
the held-out contract**: the **oracle tests** (D19) and any visible test asserting
the *discriminating* behavior (F1 throw-on-timeout, F2 the two-field split, F3 the
cap+summary). The **visible/oracle split** therefore mirrors the *shallow vs deep*
contract gradient the failure analysis found. Enriching the tree (not the prompt)
makes P's directives non-vacuous and gives V real siblings/tests to learn from;
because the tree is identical across arms, it does not confound the factors.

**Overlay-disjointness invariant (§10.4 — required).** The held-out node oracle
overlays its golden test into the candidate tree at grade time; F3 already seeds
the whole failure-analysis layer *except* `F3_TEST_REL`
([f_candidate.py:93](../../../src/agent_eval_lab/runners/f_candidate.py:93)), and
`overlay_node_oracle` raises `NodeOverlayCollision` →`tree_collision` error if a
seeded path collides with a held-out path
([node_execution.py](../../../src/agent_eval_lab/records/node_execution.py)). So
enrichment must assert, **per task**, that every seeded (visible) path is disjoint
under `prefix_collision` from that task's `held_out_files` and never adds a path
the oracle overlays/displaces — enforced by a unit test over each F task's
`NodeExecutionSpec(s)`. Otherwise enrichment silently turns an arm's runs into
`agent_failure / tree_collision`, polluting the very comparison it serves.

### B.6 Roster & size
deepseek-v4-pro, GLM-5.1, MiniMax-M3, Qwen3.6-35B. **4 arms × 4 models × 3 tasks
× k=5 = 240 attempts.** Pilot first (§G).

### B.7 Execution order + driver (§9.8 + §10.7)
A **seeded, block-randomized order** interleaving all four arms within each
`(model, task, repetition)` block, generated by a pure `ablation_run_order(seed,
…)` and frozen in the ablation spec — so provider drift / time effects can't
masquerade as a P/V effect. **This needs net-new orchestration:** today both
run paths are strictly per-condition-sequential, each writing one JSONL
(`_run_f_command`, `run_f_candidate`); nothing consumes a global order. A new
driver (CLI `run-f-ablation`) executes attempts in the frozen `ablation_run_order`
across all (model × task-arm × rep) — the arm is encoded in each run's `task_id`
(§B.2) — and writes **one artifact per condition** (`runs-ablation-{slug}-F.jsonl`,
all 12 task-arms inside). The pure order function is unit-tested; the driver
records the realized execution order in a sidecar for audit (the API-call order is
what controls drift, not the on-disk record order).

---

## PART C — Per-subset plan (F1 / F2 / F3)

Mechanism hypotheses below are **retrospective** (derived from these tasks'
failures, §8.4) and reported as descriptive narrative, not confirmed effects.

- **F1 — flaky screenshot → `waitFor` helper.** Pure contract-discovery failure
  (instant check vs poll/timeout/throw + READY branch). **P expected to
  dominate** (siblings surface the `waitFor*` pattern; the called method surfaces
  the contract). V helps only if the model authors a throw-path test. *Tree
  enrichment: the `waitFor*` siblings + the spec that calls the helper.*
- **F2 — `result.signal` + `result.confidence` as two fields.** Field-merge +
  budget runaway on 37 KB `wdio.conf.ts` + out-of-scope edits. **Both factors +
  the token-efficiency signal** matter here. *Tree enrichment: `analyzeFailure`'s
  source so its return shape is readable.*
- **F3 — Allure attachment, cap + summarize tail.** Only Qwen3.6 passed (blind
  iteration). **V expected to dominate** (the loop operationalizes Qwen3.6's
  strategy). P modest (siblings protect the 34 guard tests, don't reveal the
  cap). *Tree already broad; curate which of its tests are visible vs oracle.*

Report narrative target: **P → F1/F2 (contract discovery), V → F2/F3 (iterative
verification), P → token-efficiency on F2.**

---

## PART D — Scoring & metrics

### D.1 `pass^k` honors the declared censoring policy (§8.2)
The primary `pass_pow_k` MetricDef **declares** `censoring_policy="failure"` but
`pass_pow_k` keys only on `grade.passed`
([reliability.py:30](../../../src/agent_eval_lab/metrics/reliability.py:30)) —
unenforced. **Change:** pass iff
`grade.passed AND NOT (safety_cap_bound OR max_rounds_bound)`.
**Verified blast radius:** of **1,360** historical records, **0** have
`grade.passed=True AND safety_cap_bound=True`; the 5 `safety_cap` and 1 legacy
`max_steps` runs already failed on grade ⇒ **enforcing this moves zero existing
pass^k numbers.** (Both completion literals — `completed` (1058) and
`completed_natural` (218) — count as completions.)

**Scope is global, by design (§10.6).** `pass_pow_k`/`task_reliability`
([reliability.py:26](../../../src/agent_eval_lab/metrics/reliability.py:26)) are
domain-agnostic and shared by D/B, and the Fisher F path also routes through
`task_reliability` ([comparisons.py:62](../../../src/agent_eval_lab/experiments/comparisons.py:62)),
so the censor applies everywhere and F pass^k stays consistent with F
comparisons. This is intended: it enforces the MetricDef's *already-declared*
`censoring_policy="failure"` for every primary metric. Forward consequence to
state plainly: a D run that hits `max_rounds=50` mid-task now fails-by-censor
where a graded-correct-but-incomplete tree might previously have passed —
correct, since an uncommitted run is not a reliable success.

### D.2 Estimand is descriptive (§8.3 + §8.4 + §11.7)
`comparisons.py` supports only pairwise *condition* comparisons (Fisher exact for
F, [comparisons.py:65](../../../src/agent_eval_lab/experiments/comparisons.py:65));
no factorial machinery, and 3 base tasks give only 3 task-level obs per arm
(effective N ≈ 12 cells/arm at attempt level, k=5 correlated). The ablation is its
**own experiment** (`f_ablation_spec`); production `m1_spec`'s F domain stays the 3
original tasks, **unchanged**. So:
- **Per-arm `pass^k`**: group the 12 task-arms by arm suffix into 4 sets of 3,
  reporting each as a 3-task point estimate with the binomial/exact CI the glossary
  mandates for F. **Never a 12-task pool** (that would average across arms).
- The **`bare` arm is the within-ablation control** (enriched tree + 40-cap, shared
  with every arm), *not* a reproduction of production M1 F (minimal tree + 20-cap);
  the enrichment/cap-alone effect is a separate, looser observation, out of the 2×2.
- **Descriptive** main effect at the **attempt level** (pass@1):
  P = mean over {V=0,V=1} of (pass@1|P=1 − pass@1|P=0); symmetric for V;
  interaction = (both − prompt − feedback + bare). **No Holm, no confirmatory
  p-values.** Confirmation deferred to §F.

### D.3 Resource vs time-to-completion — don't conflate (§9.6)
- **Observed resource use (tokens, cost):** fully spent *even on capped runs*,
  so summed/aggregated over **all valid runs incl. capped**. (My earlier
  "uncensored-only" was wrong here.)
- **Time-to-natural-completion (rounds, wall-time):** right-censored on capped
  runs → survival-style summary / lower-bound (`≥X`) over uncensored, with the
  censoring count disclosed. `n_censored` includes `max_rounds_bound`.

### D.4 Harness signals — separate authored from product edits (§9.5)
- **`product_edit_count`** = writes/replaces to `target_paths` only.
- **`authored_test_edit_count`** = writes to `tests/authored/` (own axis).
- **`out_of_scope_edit_rate`** = files outside `target_paths ∪ tests/authored/`
  — so a compliant V run (which *must* write `tests/authored/`) is **not**
  mechanically penalized.
- **`run_tests` adoption rate + count** (V arms) — did the model verify at all?

---

## PART E — Classifier fc-v4 (§8.8)
ADR-0013 requires a version bump for any semantic row change (current fc-v3).
fc-v4:
1. **`node_execution` leaf fix** — `first_execution_evidence`
   ([classify.py:104](../../../src/agent_eval_lab/reports/classify.py:104))
   accepts `"node_execution"` so failing F runs classify as
   `agent_failure / oracle_red`, not catch-all `other_miss`.
2. **Budget-override reconciliation** — fire on the loop's real stop reasons:
   `max_steps` (legacy) + `safety_cap` + `max_rounds`.
3. **Row-1 guard** — `classify_run`'s `if grade.passed`
   ([classify.py:135](../../../src/agent_eval_lab/reports/classify.py:135)) is
   guarded with `and not cap_bound` so a cap-bound run classifies as
   `budget_exhausted`, not `passed` (consistent with D.1).
4. Tests per row + an ADR-0013 fc-v4 amendment; `CLASSIFIER_VERSION="fc-v4"`.
   Taxonomy outputs move (the fix); pass^k does not (D.1, verified).

---

## PART F — Held-out confirmation (deferred)
F1/F2/F3 hypotheses are retrospective. As a **separate follow-up phase**: author
untouched **F4–F6** web-dossier tasks (not used to derive any factor),
**pre-register** the same factors + descriptive→inferential plan, and run the
ablation there. No fourth factor (3 tasks can't support it). Out of scope here
beyond recording the queue item.

---

## PART G — Sequencing
Each step independently testable; provider calls only at step 6; real V sandbox
only on macOS.

1. **fc-v4 + pass^k censoring + re-emit reports.** Classifier rows (E) +
   `pass_pow_k` censoring (D.1) + tests. Re-run `reports/m1.py` over existing
   JSONL — verified **0 pass^k moves**, taxonomy corrected. No network.
2. **`max_rounds` plumbing + recorded policy fields.** loop → trajectory
   (`max_rounds`/`safety_cap`/`max_rounds_bound`) → serialize → aggregate
   (D.3 split, `n_censored`) → per-domain config (F+D). TDD with a stub loop.
3. **Arm-as-task + Factor P.** Build the 12 F task-arms (3 base × 4 arms) as
   distinct `task_id`s sharing each base task's `verification` (B.2); Factor P
   rides `messages`, arms differ only in prompt/tools. Task-scope `run_uid`. Add
   the Factor-P prompt block (B.3). **No `arm_id` / `ArmDef` / `ConditionDef` /
   report-join changes** — arm rides `task_id`, so `pass^k` separates arms for free
   and the committed frozen M1 specs stay verified. (Confirm `verify_spec_hash`.)
4. **Candidate-tree enrichment + public/held-out curation** (B.5) per F task,
   with the overlay-disjointness unit test (§10.4).
5. **Factor V sandbox.** `runners/sandboxed_node_edge.py` (seatbelt profile,
   Darwin-gated) + `make_authored_test_executor` over `tests/authored/` +
   separate tail-aware feedback rendering (B.4). Unit tests inject a fake
   executor; one macOS-only integration test asserts the sandbox **blocks** an
   `evaluator-only/` read + a network call.
6. **`run-f-ablation` driver + freeze `f_ablation_spec` → pilot → full run.**
   New driver executes the frozen seeded `ablation_run_order` across
   (model × task-arm × rep) — arm in `task_id` — and writes **one artifact per
   condition** + the realized-order sidecar (B.7, §10.7). Spec: 40-round F policy,
   the 12 task-arms × 4 models, seeded order. Pilot: 1 model × 4 arms × 3 tasks ×
   k=2 ≈ 24; then the full **240**.
7. **Descriptive report** (C narrative + D.2/D.3/D.4) + queue F4–F6 (F).

---

## 8. Pre-spec review — round 1 (all folded in)
| # | sev | finding | resolution |
|---|---|---|---|
| 1 | P0 | arms have no distinct artifact identity | §B.2 `arm_id` (revised in §9.3 to a separate field, not composite condition_id) |
| 2 | P0 | "cap-bound = fail" unimplemented | §D.1 enforce declared policy; §E reconcile+guard. 0 score moves |
| 3 | P0 | factorial estimand wrong/unsupported | §D.2 descriptive; attempt-level effects; no Holm |
| 4 | P1 | hypotheses not a-priori | §1/§C retrospective; §F held-out confirmation; no 4th factor |
| 5 | P1 | untruncated output violates ADR-0009 | §B.4 keep cap; "read full suite" → P (further revised §9.7) |
| 6 | P1 | counting censored ≠ honest medians | §D.3 (revised §9.6: observed vs time-to-completion) |
| 7 | P1 | model-authored provenance unenforced | §B.4 reserved `tests/authored/` (security boundary added §9.1) |
| 8 | P2 | classifier needs a version bump | §E fc-v4 + tests + ADR amendment |

## 9. Pre-spec review — round 2 (all folded in)
| # | sev | finding | resolution |
|---|---|---|---|
| 1 | P0 | V is a real evaluator-oracle leakage channel — model JS runs as evaluator user w/ FS+network ([node_edge.py:123](../../../src/agent_eval_lab/runners/node_edge.py:123)); reserved path ≠ isolation (D33) | §B.4 **seatbelt `sandbox-exec`** boundary: deny file-read outside temp tree + deny network; oracle path untouched; macOS-gated |
| 2 | P0 | 40-round treatment not frozen/auditable | §A.2 record `max_rounds`+`safety_cap` on every trajectory; §B.1 freeze policy in separate `f_ablation_spec.py` |
| 3 | P1 | composite `condition_id` breaks pricing ([pricing.py:67](../../../src/agent_eval_lab/experiments/pricing.py:67)) | §B.2 keep `condition_id=provider:model`; `arm_id` separate field; join on `(condition_id, arm_id)` |
| 4 | P1 | P references context F1/F2 trees lack ([f_run.py:27](../../../src/agent_eval_lab/runners/f_run.py:27)) | §B.5 enrich trees identically across arms from pinned SHA |
| 5 | P1 | edit metrics mechanically penalize V | §D.4 separate `authored_test_edit_count` from product edits/out-of-scope |
| 6 | P1 | dropping capped runs biases resource efficiency | §D.3 tokens/cost over **all** runs; rounds/wall-time censored |
| 7 | P1 | global tail truncation breaks frozen canonical contract ([ADR-0009:23](../../adr/0009-recorded-execution-output-is-canonicalized-never-verbatim.md)) | §B.4 don't touch global `truncate_output`; separate versioned V feedback rendering |
| 8 | P1 | no randomized/counterbalanced run order | §B.7 seeded block-randomized order frozen in the spec |
| 9 | P1 | "all domains" can't include B — no live B loop ([b_run.py:11](../../../src/agent_eval_lab/runners/b_run.py:11)) | §A.2/§2 Part A = F+D now; B deferred |

## 10. Pre-spec review — round 3 (all folded in)
Independent fresh-eyes pass on the round-2 resolutions. Round-2 §9.6, §9.7, §9.2,
§A.1, §9.9, and §E (fc-v4 row-1 guard) were re-verified and **hold**.

> **Superseded by the grilling pass (§11.1):** rows **#1, #2, #5** below were
> resolved by *building arm plumbing* (arm_id field, report join, ArmDef). The
> **arm-as-task** decision retires that plumbing entirely — the table rows are
> kept as the round-3 audit trail, but their live resolution is now §B.2 /§11.1.

| # | sev | finding | resolution |
|---|---|---|---|
| 1 | P0 | arm join not plumbed — report keys on `condition_id` alone ([cli.py:1171], [comparisons.py:41](../../../src/agent_eval_lab/experiments/comparisons.py:41)); 4 arms collapse, last-write-wins | §B.2 end-to-end report-side `(condition_id, arm_id)` re-key + `--runs` arm slot + cost strips `@arm` (step 3) |
| 2 | P0 | `tool_set_hash` on shared `ConditionDef` breaks committed `verify_spec_hash` (reflective hash, [spec_hash.py:32](../../../src/agent_eval_lab/experiments/spec_hash.py:32); frozen M1 specs committed) | §B.2 arm metadata on ablation-only `ArmDef`; shared frozen schema untouched; re-verify in step 3 |
| 3 | P0 | seatbelt "deny read outside tree" stops node starting; broad read-allow reopens the leak (stdout return channel) | §B.4 deny-read-by-default + explicit read-allowlist (temp+node+system); deny network/write-outside; Docker fallback; integration test |
| 4 | P1 | tree enrichment can collide with the F3 held-out overlay → `tree_collision` ([f_candidate.py:93](../../../src/agent_eval_lab/runners/f_candidate.py:93)) | §B.5 per-task overlay-disjointness invariant + unit test |
| 5 | P1 | `arm_id` net-new on write/serialize side; fixed artifact filename ([cli.py:908](../../../src/agent_eval_lab/cli.py:908), [serialize.py:194](../../../src/agent_eval_lab/records/serialize.py:194)) | §B.2 `RunResult.arm_id` + round-trip default + arm-aware filename |
| 6 | P1 | D.1 censor is in shared `reliability.py` → applies to D/B too | §D.1 scope made explicit (global, by design; forward consequence stated) |
| 7 | P2 | interleaved order has no orchestration — paths are per-condition-sequential | §B.7 net-new `run-f-ablation` driver + realized-order sidecar (step 6) |
| 8 | P2 | `run_tests` ToolDef says "Run pytest"; request snapshots whole tree ([code_world.py:83](../../../src/agent_eval_lab/tools/code_world.py:83)) | §B.4 V-specific node-accurate ToolDef; executor restricts to `tests/authored/` |

## 11. Design grilling — CONTEXT-grounded (all folded in)
A `/grill-with-docs` pass against `CONTEXT.md` + `docs/adr/`. Each decision below
updated the glossary and/or an ADR **inline**; the spec was then aligned.

| # | branch | decision | glossary / ADR | spec |
|---|---|---|---|---|
| 11.1 | arm identity | **arm = distinct `task_id`** (M2 pattern); retire `arm_id`/`ArmDef`/report-join | `arm` (new) | §B.1/§B.2; retires §10.1/§10.2/§10.5 |
| 11.2 | turn-bound name | **`max_rounds`** caps `rounds`; runner-level `max_steps` **superseded** | `max_rounds`, `max_steps`; ADR-0017 | §A.2 |
| 11.3 | budget granularity | per-domain default + per-task `metadata.max_rounds` override | `max_rounds`; ADR-0017 | §A.2 |
| 11.4 | test vocabulary | **`visible tests`** (not "public"); new **`authored tests`**; node-generalize code-world | `visible tests`, `authored tests`, `code-world`, `execution edge` | §B.3/§B.4/§B.5/§C |
| 11.5 | isolation tier | V uses **`confined execution`** (seatbelt/kernel), distinct from trusted `sandbox` | `confined execution`, `sandbox`; ADR-0016 | §B.4 |
| 11.6 | enrichment curation | include what P names; exclude discriminating-behavior tests; reuse `prefix_collision` conformance | (spec-level) | §B.5 |
| 11.7 | aggregation | ablation = own spec; per-arm `pass^k` (4×3), never a 12-task pool; `bare`=control | (spec-level) | §D.2 |
| 11.8 | censoring + uid | `censoring` covers `max_rounds`, tokens/cost observed; `run_uid` **task-scoped** | `censoring`, `run_uid` | §A.2/§B.2/§D.3 |
| 11.9 | driver | `run-f-ablation`; one artifact per condition; realized-order sidecar | (spec-level) | §B.7/§G6 |

Net effect: **arm-as-task (11.1) shrank the build** (three round-3 findings
retired); the rest aligned spec vocabulary to the locked glossary and minted
**ADR-0016** (confined execution) + **ADR-0017** (loop budget).
