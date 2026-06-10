# Agent Eval Lab — Design: Eval Pipeline → Dataset Engineering → Finetuning

- **Date:** 2026-06-09
- **Status:** Draft for review
- **Scope:** the full program, one document. Phase 1 (eval) is the committed core; Phases 2–3 are designed now so the data model does not need rework later.

This document is the "why" record for the project. It is intended to be read by a
future maintainer (or interviewer) who wants to understand not just *what* was
built but *which decisions were made and why*. Decisions and their rationale are
called out inline and collected in §14.

---

## 1. Purpose & context

`agent-eval-lab` is simultaneously a **learning vehicle** and a **public
portfolio artifact**. It exists to turn agent-evaluation concepts (from *AI
Engineering*, Chip Huyen — hereafter **AIE**) into working, reproducible evidence
and to demonstrate the skills in the target job description (JD): building
capability-discriminating eval datasets, reliable eval infrastructure, failure
analysis, dataset engineering, and finetuning.

The unifying thread is **one model lineage (Qwen) flowing through three phases**,
with the project's own eval as the measuring instrument throughout:

```
my dataset engineering  →  my finetuned model  →  measured by my eval
```

### JD ↔ AIE ↔ phase mapping

| JD requirement | AIE chapters | Phase |
|---|---|---|
| #1 capability-discriminating eval datasets (planning / tool-use / multi-turn / instruction-following); iterate the standard | Ch 3 Evaluation methodology, Ch 4 Evaluate AI systems, Ch 6 Agents | Phase 1 |
| #2 training corpora for code-gen / general agent; multi-dimensional e2e assessment | Ch 8 Dataset engineering, Ch 5 Prompt eng | Phase 2 |
| #3 annotation strategy → agent capability; data + RL; controllability detection | Ch 7 Finetuning, Ch 8 | Phase 2→3 |
| #4 analyze failure modes (from using Claude Code / OpenClaw); build gap-filling data + boundary tests | failure analysis + Ch 8 | Phase 1 (feeds 2) |

### The reframe that shapes everything

In mid-2026, **single-run `pass@1` accuracy no longer discriminates frontier
models** — public benchmarks saturate within months and several are
contaminated. The differentiated skill (and the JD's actual ask) is to build a
**bespoke, contamination-free eval** that reports **reliability (pass^k /
consistency across repeated runs) and per-run cost/latency**, not a single
accuracy number. We borrow *architecture* from public benchmarks, not their data.

---

## 2. Scope, phasing, and the two portfolio releases

Priority, fixed by the project owner: **deep eval > dataset engineering >
finetuning**. Evaluation is the foundation the other two stand on — you cannot
show that engineered data or finetuning *helped* without an eval that measures
it.

The project ships **two independent portfolio releases** so that finetuning can
never delay or jeopardize the eval-system release (this is a deliberate guard
against the project drifting into a half-finished "ML training lab"):

- **Release #1 — Evaluation portfolio (Weeks 1–12).** Has **no training
  dependency**. This is the JD#1/#4 deliverable and stands alone.
- **Release #2 — Data + finetuning (Weeks 13–16).** Builds on Release #1's
  artifacts; closes the "my data → my model → my eval" loop.

### Constraints (fixed inputs)

- **Models / access:** native dedicated keys for DeepSeek, Zhipu GLM, MiniMax,
  Alibaba Qwen (DashScope); **OpenRouter** as the gateway for everything else
  (e.g. a top-tier ceiling model). One open model (Qwen3-8B) runs locally.
- **Finetuning hardware:** Apple Silicon **Mac M5 (unified memory)** → the
  toolchain is **MLX** (`mlx-lm`), *not* the CUDA stack (Unsloth/axolotl/TRL).
- **Time:** ~20h/week.
- **First capability:** tool use & function-calling. **Domain:** synthetic
  tool-world for tool-use/multi-turn/instruction tasks + small real repos for
  code-repair.

---

## 3. Architecture

Keeps the repo's existing **functional-core / imperative-shell** decision
([docs/ARCHITECTURE.md](../../ARCHITECTURE.md)). Pure transformations in the
core; model calls, process execution, and I/O at explicit edges that return
plain data.

### Module layout

```
agent_eval_lab/
  tasks/        Task schema + validation (PURE) · dataset loaders (edge)
  tools/        Synthetic tool-world: JSON tool schemas + deterministic
                implementations over explicit in-memory state (PURE)   ← added
  runners/      IMPERATIVE SHELL: provider client, model↔tool loop,
                retries/limits → emits Trajectory records
  graders/      PURE scorers: exact_match (exists), ast_tool_match,
                constraint interpreters, llm_judge (prompt pure; call at edge)
  metrics/      PURE aggregation: pass@k, pass^k, cost/latency, bootstrap CIs
  reports/      PURE report models + rendering · file I/O (edge)
  experiments/  ExperimentSpec/Result + analysis (PURE) · orchestration (edge)
  data/         (Phase 2) generators, flywheel mining, dataset cards
  finetune/     (Phase 3) TrajectoryExample export, MLX SFT, closed-loop re-eval
```

`tools/` is the one addition to the original plan — it is what makes a
*deterministic synthetic tool-world* possible.

### Provider abstraction

All target providers speak the **OpenAI-compatible `/chat/completions`** shape,
so there is exactly one client parameterized by config:

```python
@frozen(kw_only=True)
class ProviderConfig:
    id: str            # "deepseek" | "glm" | "minimax" | "qwen" | "openrouter" | "local"
    base_url: str
    api_key_env: str   # env var NAME holding the dedicated key (never the key)
    model_id: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)  # not a shared {} default
    adapter: str | None = None   # optional PURE normalizer for tool-call dialect quirks
```

```
deepseek-v4    → api.deepseek.com               key=DEEPSEEK_API_KEY   (dedicated)
glm-5          → open.bigmodel.cn/api/paas/v4   key=ZHIPU_API_KEY      (dedicated)
minimax-m2.1   → api.minimax.io/v1              key=MINIMAX_API_KEY    (dedicated)
qwen3-max      → dashscope…/compatible-mode/v1  key=DASHSCOPE_API_KEY  (dedicated)
gpt/claude/…   → openrouter.ai/api/v1           key=OPENROUTER_API_KEY (gateway)
qwen3-8b-local → localhost:11434/v1 (Ollama/MLX)                       (no key)
```

"OpenAI-compatible" is only ~90% true for tool-calling; per-provider `adapter`
functions (pure request/response normalizers) absorb dialect differences at the
edge so the core only ever sees canonical `ToolCall`/`Turn` records.

---

## 4. Data model (the locked spine)

Every record is a frozen dataclass (`kw_only=True`), serializable to JSONL.
**Datasets, traces, metrics, and usage are immutable records.**

### 4.1 Tool calls — spec-time vs run-time are distinct types

`call_id` is generated at runtime and is unknowable when authoring an expected
value, so the expected and observed calls are *different types*:

```python
@frozen(kw_only=True)
class ExpectedToolCall:          # spec-time: no call_id
    name: str
    arguments: Mapping[str, Any]

@frozen(kw_only=True)
class ToolCall:                  # run-time: has call_id
    call_id: str
    name: str
    arguments: Mapping[str, Any]
```

### 4.2 Turns — tagged union with explicit discriminators

```python
@frozen(kw_only=True)
class MessageTurn:
    type: Literal["message"] = "message"
    role: Literal["system", "user", "assistant"]
    content: str

@frozen(kw_only=True)
class ToolCallTurn:
    type: Literal["tool_call"] = "tool_call"
    tool_calls: tuple[ToolCall, ...]            # supports parallel calls
    content: str | None = None

@frozen(kw_only=True)
class ToolSuccess: type: Literal["success"] = "success"; result: Any
@frozen(kw_only=True)
class ToolFailure: type: Literal["failure"] = "failure"; error: str
ToolOutcome = ToolSuccess | ToolFailure         # ok/error mutually exclusive by construction

@frozen(kw_only=True)
class ToolResultTurn:
    type: Literal["tool_result"] = "tool_result"
    call_id: str                                # links result to its call
    outcome: ToolOutcome

Turn = MessageTurn | ToolCallTurn | ToolResultTurn
```

The `type` discriminator is required for reliable JSON round-tripping and for the
pure grader's `match` dispatch.

### 4.3 Verification — a real tagged union (illegal states unrepresentable)

Each variant carries **only** the fields that variant needs; there are no
nullable "maybe this kind, maybe that kind" fields:

```python
@frozen(kw_only=True)
class OutputMatchSpec:
    type: Literal["output_match"] = "output_match"
    expected_output: str
    normalizer: str | None = None

@frozen(kw_only=True)
class ToolCallMatchSpec:
    type: Literal["tool_call_match"] = "tool_call_match"
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"

@frozen(kw_only=True)
class FinalStateSpec:
    type: Literal["final_state"] = "final_state"
    constraints: tuple[StateConstraint, ...]

@frozen(kw_only=True)
class TrajectorySpec:
    type: Literal["trajectory"] = "trajectory"
    constraints: tuple[TrajectoryConstraint, ...]

@frozen(kw_only=True)
class ExecutionSpec:
    type: Literal["execution"] = "execution"
    test_command: str
    timeout_s: int

@frozen(kw_only=True)
class LlmJudgeSpec:
    type: Literal["llm_judge"] = "llm_judge"
    rubric: str
    judge_model: str
    scale: tuple[int, int] = (1, 5)

@frozen(kw_only=True)
class AllOf:                                      # composition / conjunction
    type: Literal["all_of"] = "all_of"
    specs: tuple["VerificationSpec", ...]

VerificationSpec = (OutputMatchSpec | ToolCallMatchSpec | FinalStateSpec
                    | TrajectorySpec | ExecutionSpec | LlmJudgeSpec | AllOf)
```

**Constraints are data variants, interpreted by a pure grader** (behavior lives
in functions, not on records, so records stay serializable):

```python
# state
@frozen(kw_only=True)
class StateEquals:   type: Literal["state_equals"] = "state_equals";     path: str; value: Any
@frozen(kw_only=True)
class StateContains: type: Literal["state_contains"] = "state_contains"; path: str; value: Any
StateConstraint = StateEquals | StateContains
# trajectory (policy / side-effect discipline)
@frozen(kw_only=True)
class NoToolCall:   type: Literal["no_tool_call"] = "no_tool_call";     name: str
@frozen(kw_only=True)
class OnlyModifies: type: Literal["only_modifies"] = "only_modifies";   paths: tuple[str, ...]
@frozen(kw_only=True)
class MaxToolCalls: type: Literal["max_tool_calls"] = "max_tool_calls"; n: int
TrajectoryConstraint = NoToolCall | OnlyModifies | MaxToolCalls
```

Composite example — "close the ticket **and** harm nothing":

```python
AllOf(specs=(
    FinalStateSpec(constraints=(StateEquals(path="tickets.T-1.status", value="closed"),)),
    TrajectorySpec(constraints=(NoToolCall(name="send_email"),
                                OnlyModifies(paths=("tickets.T-1",)),
                                MaxToolCalls(n=4))),
))
```

### 4.4 Task

```python
@frozen(kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput                      # message(s) + available_tools (JSON schemas)
    verification: VerificationSpec
    metadata: TaskMetadata                # split, version, provenance, world_template_id, difficulty_knob
    initial_state: Mapping[str, Any] | None = None
    scripted_user: "ScriptedUser | None" = None   # multi-turn only (Phase 1b)
```

`kw_only=True` resolves the "default before required field" ordering problem.

### 4.5 Grading layer

```python
FailureCategory = Literal[
    "malformed_call", "schema_violation", "wrong_tool", "wrong_args",
    "missing_call", "extra_call", "order_mismatch",
    "forbidden_action", "step_limit_exceeded",
]

@frozen(kw_only=True)
class GradeResult:
    grader_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any]                   # what the grader saw (audit/trace)
    failure_reason: FailureCategory | None = None # structured → feeds JD#4 taxonomy

@frozen(kw_only=True)
class RunResult:
    task_id: str
    condition_id: str
    run_index: int
    trajectory: Trajectory
    grade: GradeResult
```

> **Current checkout** has `GradeResult{passed, score, feedback}` only
> ([exact_match.py](../../../src/agent_eval_lab/graders/exact_match.py)). The
> `evidence` / `failure_reason` fields and everything above are **proposed**
> (see §13).

### 4.6 Metrics & experiments

```python
@frozen(kw_only=True)
class MetricDef:
    name: str                                     # "pass^3", "pass@1", "cost_per_correct"
    estimand: Literal["task_reliability", "trial_accuracy", "cost", "latency"]
    k: int | None = None
    unit_of_analysis: Literal["task"] = "task"
    resampling: Literal["cluster_bootstrap_by_task"] = "cluster_bootstrap_by_task"
    paired: bool = True

@frozen(kw_only=True)
class ExperimentSpec:                              # pre-registered, immutable
    id: str
    hypothesis: str
    dataset_id: str
    dataset_version: str
    split: Literal["dev", "held_out"]
    conditions: tuple[Condition, ...]
    primary_metric: MetricDef
    secondary_metrics: tuple[MetricDef, ...] = ()
    planned_comparisons: tuple[ComparisonSpec, ...] = ()
    decision_rule: DecisionRule
    n_trials: int
    n_trials_meaning: Literal["per_task", "total"]
    seed_policy: SeedPolicy
    spec_hash: str                                # content hash over canonical JSON

@frozen(kw_only=True)
class StructuredConclusion:
    outcome: Literal["supported", "refuted", "inconclusive"]
    primary_metric_value: float
    ci: tuple[float, float]
    explanation: str

@frozen(kw_only=True)
class ExperimentResult:                           # post-run, references spec, never mutates it
    spec_id: str
    spec_hash: str
    dataset_version_used: str                     # recorded → reconcile vs spec
    seeds_used: tuple[int, ...]
    per_condition: tuple[ConditionMetrics, ...]   # aggregates GradeResults
    comparisons: tuple[ComparisonResult, ...]     # ONLY the pre-registered ones
    conclusion: StructuredConclusion
```

**`pass^k` formal definition:** a task *passes* iff **all k independent runs
pass**, under a fixed task spec with varying model seed. The estimand is
**task-level reliability** = proportion of tasks that pass all k runs — *not*
trial-level accuracy. CIs use **cluster (block) bootstrap resampling by task**
(all k runs of a sampled task move together); conditions are compared on the
**same paired tasks**. Treating k runs as independent would falsely narrow CIs.

**Tamper-evidence is detection, not prevention.** `spec_hash` +
`dataset_version_used` + `seeds_used` + restricting `comparisons` to
`planned_comparisons` let a verifier *reconcile* a result against its spec and
flag deviation. Actually *enforcing* that the run honored the spec is the
runner's job (it reads the spec, uses those seeds, computes only those
comparisons). **Types detect; the runner enforces.**

**Immutability caveat:** Python frozen dataclasses do not deep-freeze nested
`Mapping`/`Any`. We treat nested structures as immutable-by-convention enforced
at construction, and compute `spec_hash` over a **canonical JSON serialization**
(sorted keys) so hashing is stable regardless of dict ordering.

### 4.7 Training export type (Phase 3, defined early)

To prevent train/eval interface mismatch (the serialized SFT conversation must
match the exact Qwen chat template and tool-calling format used at inference),
the canonical export type is defined now and round-trip tested:

```python
@frozen(kw_only=True)
class TrajectoryExample:
    task_id: str
    messages: tuple[Turn, ...]          # canonical conversation
    target: str                          # rendered per the model's chat template
    provenance: Literal["strong_model_fixed", "human_fixed", "generated"]
```

Round-trip test: `TrajectoryExample` → render → parse back through the **actual
local inference client** → must reproduce the same `Turn` sequence.

---

## 5. The synthetic tool-world (`workspace-world`)

A small, self-contained fake ecosystem. Each tool is **two things**: a JSON
schema (fed to the model as `available_tools`) and a *pure* implementation
`apply(tool, args, state) -> (state', result)`. The runner (edge) holds state and
threads it explicitly; tool logic stays pure and replayable from `initial_state`.

```
tools:  search_docs(query) · get_account(user_id) · create_ticket(title, prio)
        update_ticket(id, status) · list_tickets(status?) · send_email(to, subj, body)
        ask_user(slot)                                   ← first-class clarification tool
state:  { tickets, emails, docs, accounts }
```

**Schema validation at the runtime boundary (not just the grader):** `apply`
validates args against the tool's JSON Schema and returns a `ToolFailure` on
violation — exactly as a real API returns 400. Schema-invalid calls surface as
`ToolFailure` in the trajectory *and* as a grader `schema_violation`; the world
and the grader agree on what "invalid" means, and the grader never silently
repairs a bad argument.

**Two verification modes, by design:**
- `ToolCallMatchSpec` grades the *action chosen* (path-sensitive) — tool
  selection / argument extraction.
- `FinalStateSpec` (+ `TrajectorySpec`) grades the *outcome* (path-independent) —
  multiple valid paths pass, **but** trajectory constraints forbid harmful
  side-effects along the way.

**Deterministic multi-turn (scripted user):** clarification is the explicit
`ask_user(slot=...)` tool, so detecting "the agent is asking" needs no fragile NL
parsing. The task carries a `ScriptedUser`:

```python
@frozen(kw_only=True)
class ClarificationRule: slot: str; reply: str
@frozen(kw_only=True)
class ScriptedUser:
    responses: tuple[ClarificationRule, ...]
    fallback: str = "I don't have that information."
    max_turns: int
```

This is fully replayable and identical across models → fair comparison.
**Tradeoff (stated honestly):** scripted = reproducible but rigid; an
LLM-simulated user (τ-bench style) is realistic but noisy/non-reproducible. The
comparison core uses the scripted user; an LLM-user is an optional mode reported
*separately*, never mixed into headline numbers.

**Honest scope of "auto-scorable":** a deterministic world is **auto-scorable
against deterministic state oracles**. It does *not* by itself guarantee the task
is unambiguous, the grader is correct, or the intended capability is isolated.
Those are bought separately by conformance tests, spot audits, and adversarial
generated cases (§8, §9).

**Difficulty knobs** (what lets the dataset draw a capability boundary):
distractor-tool count, argument complexity (nested/enums/dates), multi-step
depth, deliberate ambiguity (forces `ask_user`), and layered instruction
constraints.

---

## 6. Graders

### Layered strategy — "cheapest grader that works" (AIE Ch 3)

```
Tier 1  DETERMINISTIC (free, reproducible)
        OutputMatchSpec · ToolCallMatchSpec · FinalStateSpec · TrajectorySpec
Tier 2  EXECUTION (objective, isolated)
        ExecutionSpec → run tests in a sandbox; tests are the oracle   (code-repair)
Tier 3  LLM-AS-JUDGE (costly, noisy — last resort)
        LlmJudgeSpec → only for irreducibly subjective qualities
```

### AST tool-call grading (schema-first pipeline)

```
1. parse provider output         → else malformed_call
2. validate raw args vs schema    → else schema_violation        (NEVER coerced)
3. canonicalize ONLY proven-equivalent forms (key order, equal date encodings)
4. structural compare vs ExpectedToolCall → wrong_tool | wrong_args | order_mismatch
```

Canonicalization is strictly value-preserving; type coercion (`"1"` where an int
is required) is a `schema_violation`, not a silent pass. `match` modes:
`exact_sequence` (ordered) | `multiset` (order-free, duplicates preserved). There
is no `first` mode — "only the first call is allowed" is expressed as
`AllOf(prefix-match, MaxToolCalls(1))` so later/harmful calls are still graded.

`exact_match` (current checkout) survives as the `OutputMatchSpec` scorer.

### LLM-judge calibration protocol (when Tier 3 is first used)

The rule: **never trust a judge you have not calibrated**, and **establish human
reliability before judging the judge**.

1. Written rubric with an anchored scale; blind labeling.
2. **≥2 human annotators** on a shared subset → report **human–human** reliability
   *first* (κ / Krippendorff α + CI). If humans don't agree, the rubric is the
   problem — fix it before involving a model.
3. Then **judge–human** agreement, reported *separately*, with a confusion matrix
   and bootstrap CI on κ.
4. For imbalanced categories, report **Krippendorff α / Gwet AC1 / per-class F1**,
   not κ alone.
5. Below threshold → **revise the rubric or drop the quality**, *never* "fall back
   to deterministic" (deterministic was never an option for this quality, or a
   judge wouldn't have been used). Deterministic + judge *coexist* on one task via
   `AllOf`: the deterministic part checks the verifiable component and always
   runs; the judge handles only the irreducibly subjective residue.
6. Re-run calibration whenever `judge_model` changes (judges drift).

---

## 7. Metrics, experiments, and leakage-safe splits

### The two controlled experiments (Weeks 7–8)

Both use `ExperimentSpec` (pre-registered) → `ExperimentResult` (recorded), so
the statistics work is *realized inside the eval*, not studied separately.

- **E1 — roadmap question:** *Does a more precise tool description improve
  tool-selection accuracy?* Conditions `vague` vs `precise`; one pre-registered
  comparison (no fishing); decision rule = precise wins iff mean higher **and**
  95% bootstrap CI of the paired difference excludes 0.
- **E2 — model comparison, pre-registered:** *Among DeepSeek V4 / Qwen3-Max /
  MiniMax M2.1 / GLM-5 / Claude (ceiling) / Qwen3-8B-local, which is most
  **reliable** (`pass^3`) at argument extraction, and at what cost?* Multiple
  pairwise comparisons → pre-specified **and** Holm/Bonferroni corrected
  (controls family-wise error). Output: a **reliability-vs-cost Pareto chart** —
  the "capability boundary + cost" artifact.

### Leakage-safe split & isolation policy (the headline benchmark's integrity)

The biggest threat to the closed-loop claim is **train/eval leakage** — Phase-1
failures become *both* new eval tasks *and* training data. Row-level held-out is
insufficient if the same generator template, seed, missing-slot pattern, or
failure family appears on both sides.

**Policy:**
- The headline held-out benchmark is **frozen before any training** and protected
  by a **never-train manifest** (content hashes of every held-out item).
- The **isolation boundary is `world_template_id` + seed family** (a *seed family*
  = all tasks generated from one base random seed / its derived seeds for a
  template): a template and its seed family belong to *exactly one* of {train,
  dev, held-out} and never span partitions.
- `capability` and `difficulty_knob` are **stratified within** each partition for
  coverage — they are *not* the isolation boundary.
- A CI check fails the build if any training item's hash appears in the never-train
  manifest, or if a `world_template_id`/seed family crosses partitions.

---

## 8. Harness conformance check (renamed from "proof of correctness")

Two harnesses agreeing proves *agreement*, not correctness. So:

- **Primary evidence — golden conformance suite:** hand-verified recorded
  trajectories with known-correct grades, covering malformed calls, schema
  violations, ordering, duplicate calls, forbidden actions, and path-independent
  success. Graded through our harness, must match the oracle. Unit-testable, runs
  in CI, fits the repo's TDD discipline.
- **Secondary — Inspect AI differential check:** wrap 1–2 tasks as Inspect
  `Task`s; run the same model through both harnesses; agreement is
  *corroboration*, divergence is a *flag* (harness bug → fix; or grading-semantics
  difference → document). Neither is proof on its own.

This is the executable form of the README promise "distinguish agent failures
from harness failures."

---

## 9. Phase 2 — Dataset engineering / the data flywheel (Weeks 9–14; JD#2,#3)

Failure *mining* starts in Weeks 9–10 (alongside the multi-turn work, before
Release #1); the *generator*, dataset cards, and curated SFT set land in Weeks
13–14 (Release #2).

Phase 1 emits traces + `GradeResult`s tagged with `failure_reason`. That exhaust
becomes fuel:

```
Phase-1 failures ─┬→ new HARD eval tasks (regressions → grow toward the boundary)
                  └→ TRAINING data: SFT correct trajectories (one curated set, committed)
```

- **Synthetic generation:** parametrize `workspace-world` (slots, distractors,
  constraints, difficulty) → generate tasks at scale; auto-scorable against the
  deterministic state oracle. **Add adversarial generated cases + spot audits** so
  "auto-scorable" doesn't hide ambiguity/grader bugs.
- **Minimal dataset card first** (expand later only if needed): schema version,
  item count, provenance counts, capability×difficulty counts, duplicate-hash
  count, auto-verification pass rate, held-out status.
- **Contamination is three distinct checks:** `internal_leakage_check`
  (generated train/test overlap), `template_overlap_check` (template/seed family
  crossing), optional `public_benchmark_similarity_check`.
- Provenance on every item; append-only versions.
- **Committed deliverable:** *one curated SFT dataset*. DPO preference pairs and
  the annotation-strategy comparison are **stretch** (see §10).

---

## 10. Phase 3 — Finetuning on MLX + the closed loop (Weeks 15–16; JD#3)

- **Base:** Qwen3-8B (Apache-2.0, strong tool-use), or Qwen3.5-4B if M5 RAM is
  tight; same model that runs locally as an eval target.
- **Toolchain:** `mlx-lm` LoRA/QLoRA SFT. **Committed deliverable = one SFT
  adapter + closed-loop re-eval vs base with bootstrap CIs + a capability
  regression matrix.**

**Closed loop (portfolio headline):**

```
curated SFT data → finetune Qwen3-8B (MLX) → re-evaluate in the Phase-1 harness
                 → Did pass^3 reliability rise vs base, on the FROZEN held-out, with CIs?
```

**Controllability detection (JD#3):** use the eval to ask whether gains are
*controlled*, not just present — held-out never seen in training; a
**capability-regression matrix** (did improving tool-use hurt
instruction-following?); a generalization probe (train easy, test hard).

**Stretch (only if Phase 2 finishes early):**
- **DPO** on *matched* preference pairs (comparable prompt/schema/observation/
  length/answer-style; record *why* the rejected trace is rejected — so DPO learns
  competence, not artifacts).
- **Annotation-strategy experiment:** **two strategies max** (e.g.
  `strong_model_fixed` vs `human_fixed`, *or* `final_state_only` vs
  `full_trajectory`), pre-registered target + collateral metrics.
- **Agent-RL (GRPO):** needs CUDA → a short rented-GPU detour; our deterministic
  graders *are* the verifiable reward function (the same AST/state scorers).

---

## 11. Roadmap (16 weeks, two releases)

| Wk | Deliverable | Eng / Stats focus |
|---|---|---|
| 1–2 | Tool-use slice: locked `VerificationSpec` subset, `workspace-world` (2–3 tools + schema validation), AST grader + failure taxonomy, provider client, runner w/ limits, **multi-run from day 1**, initial golden conformance suite, baseline report | boundaries; pure core / effectful edges; actions·calculations·data |
| 3–4 | Taxonomy + rubric, 50 reviewed tasks, `FinalStateSpec`+`AllOf`/`TrajectorySpec`, first LLM-judge **+ calibration (κ, 2 annotators)**, failure-mode report, 2-config comparison | probability/RV, expectation/variance, estimators/CIs |
| 5–6 | 10–20 code-repair tasks, `ExecutionSpec` graders, isolated reproducible envs, task/agent/harness failure classification | TDD, boundary+integration testing, reproducibility |
| 7–8 | **E1 + E2** via `ExperimentSpec/Result`, cluster bootstrap, Holm correction, trace analysis, **Inspect conformance check** | hypothesis testing, bootstrap CIs, regression, multiple-testing |
| 9–10 | Multi-turn failure modes + **scripted-user protocol**, flywheel mining, **leakage-safe splits + never-train manifest**, agent-vs-eval-defect report | — |
| 11–12 | **Portfolio Release #1** (eval): README, arch diagram, dataset docs, reproducible commands, CI, 2 experiments, failure analysis, limitations, technical article — **no training dependency** | — |
| 13–14 | Synthetic generator, append-only versions, **minimal dataset cards**, three contamination checks, **one curated SFT dataset**, `TrajectoryExample` export + round-trip tests | — |
| 15–16 | **MLX SFT only** + base-vs-adapter closed-loop eval + bootstrap CIs + **capability regression matrix** → **Portfolio Release #2**. Stretch: DPO, annotation-strategy, RL | — |

---

## 12. Testing / CI

- **Pure core** (graders, normalization, metrics, verification dispatch) → unit
  tests, **no mocks**, red-green-refactor.
- **Edges** (provider client, runner, sandbox, I/O) → integration tests with
  **recorded fixtures** (VCR-style API cassettes; recorded trajectories).
- **Golden conformance suite** → the correctness oracle, in CI.
- **Property-based tests** (Hypothesis): canonicalization is idempotent; a
  schema-invalid arg *never* grades as pass; same seed+input → same trajectory
  hash (determinism guard).
- **Leakage CI gate**: never-train manifest + partition-crossing check.
- Extends the existing `pytest` + `ruff` CI.

---

## 13. Current checkout vs proposed (delta)

| Area | Current checkout | Proposed | Status |
|---|---|---|---|
| Graders | `grade_exact_match` only; `GradeResult{passed, score, feedback}` | + `evidence`, `failure_reason`; AST tool grader; constraint interpreters; judge | ✅ landed (slice 001): `evidence`/`failure_reason` present; AST tool grader with 7-category taxonomy; `grade_exact_match` → `OutputMatchSpec` scorer |
| Dataset | `tool_selection.jsonl`: name-only `expected`, no schemas/args/match-mode | `Task` with `VerificationSpec`, `initial_state`, JSON-schema tools, provenance | ✅ landed (slice 001): `tool_use.jsonl` with full `Task` records, ~20 tasks, both match modes |
| Modules | `graders/` only | + `tasks/ tools/ runners/ metrics/ reports/ experiments/ data/ finetune/` | ✅ landed (slice 001): `tasks/ tools/ runners/ metrics/ reports/` all present; `experiments/ data/ finetune/` not yet |
| Runs | none | `Trajectory`, multi-run, cost/latency capture | ✅ landed (slice 001): `Trajectory` with turns/usage/cost/latency/run_index/termination_reason; k runs per task |
| Experiments | none | `ExperimentSpec/Result`, leakage-safe splits | not yet |

The current seed dataset and exact-match grader are a valid *first vertical
slice*; this design extends them, it does not contradict them.

---

## 14. Decisions & rationale log

1. **Build own harness + cross-validate vs Inspect** (not adopt, not pure
   scratch). Best portfolio signal + best learning + keeps FP/TDD; cross-check de-
   risks harness bugs. JD rewards harness builders.
2. **Native dedicated keys per subscription + OpenRouter gateway for the rest.**
   One OpenAI-compatible client + per-provider config; `adapter` absorbs
   tool-call dialect quirks at the edge.
3. **Synthetic tool-world + small real repos.** Synthetic = zero contamination,
   deterministic oracles, scalable generation; real repos = realism for
   code-repair only, where execution is the oracle.
4. **Reliability (`pass^k`) + cost from day 1.** 2026 reality; cheap upfront,
   expensive to retrofit into a single-run data model.
5. **Tagged-union `VerificationSpec`, distinct spec/runtime tool-call types,
   sum-typed outcomes.** Make illegal states unrepresentable; keep records pure
   data interpreted by pure graders.
6. **Composite verification (outcome AND policy).** Path-independence must not
   mean "ignore harmful actions."
7. **Schema-first grading, never repair.** The grader must not be more lenient
   than the runtime; coercion is a `schema_violation`.
8. **Deterministic scripted user via `ask_user`.** Reproducibility/fairness over
   realism for the comparison core; LLM-user is an optional separate mode.
9. **`pass^k` = task-level reliability; cluster bootstrap by task; paired.**
   Avoids falsely narrow CIs.
10. **Two portfolio releases; finetuning never blocks the eval release.** Protects
    the JD#1 core; honors the original 12-week identity.
11. **Leakage isolation by `world_template_id` + seed family; frozen held-out +
    never-train manifest.** The closed-loop result must survive "it just memorized
    the generator."
12. **Phase 3 committed scope = one SFT adapter + re-eval.** DPO / annotation-
    strategy / RL are stretch — avoids a shallow two-week demo.

---

## 15. Risks, limitations, open questions

- **Causal validity / leakage** — primary risk; mitigated by §7 isolation policy
  and the §12 CI gate. Still the thing most worth attacking in review.
- **MLX maturity** — `mlx-lm` SFT/LoRA is solid; agent-RL (GRPO) is not local →
  flagged CUDA stretch only.
- **Judge reliability** — gated behind human-human reliability; judge is never the
  sole oracle where a deterministic check exists.
- **Scope creep** — mitigated by two releases + explicit stretch flags.
- **Open question (non-blocking):** for code-repair (Weeks 5–6), which real repos
  / sandbox mechanism (container vs `venv` + subprocess) on macOS? Decide at the
  Phase-1b boundary; does not affect the locked types.

---

## 16. Next step

On approval of this design, proceed to **writing-plans** for the **Weeks 1–2
tool-use vertical slice** (the only part that needs an implementation plan now):
locked `VerificationSpec` subset, `workspace-world` with schema validation, AST
grader + failure taxonomy, provider client, multi-run runner, initial golden
conformance suite, baseline report.
