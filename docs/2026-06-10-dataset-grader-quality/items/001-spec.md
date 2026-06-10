# Item 001 — Composite verification layer

- **Run:** `docs/2026-06-10-dataset-grader-quality`
- **Date:** 2026-06-10
- **Realizes:** design doc §4.3 (verification tagged union), §4.5 (grading layer),
  §5 (two verification modes), §6 (graders), §14 decision 6 (outcome AND policy)
- **Extends (current checkout):** `tasks/schema.py`, `tasks/parse.py`,
  `graders/dispatch.py`, `graders/tool_call.py`, `records/grade.py`,
  `records/trajectory.py`, `records/serialize.py`, `runners/loop.py`,
  `runners/multi_run.py`, `tools/workspace.py`, `tests/test_golden_conformance.py`

## Goal

Extend the locked `VerificationSpec` union from its Weeks 1-2 subset
(`OutputMatchSpec | ToolCallMatchSpec`) to the design's full deterministic tier by
adding `FinalStateSpec`, `TrajectorySpec`, and `AllOf`. Final-state and trajectory
verification grade the *outcome* and the *policy* of a run (path-independent: many
valid tool paths reach the same world-state, but harmful side-effects along the way
are forbidden), which is exactly the capability-discriminating signal the v2 dataset
(item 002) needs. The five constraint data variants (`StateEquals`, `StateContains`,
`NoToolCall`, `OnlyModifies`, `MaxToolCalls`) stay pure serializable data interpreted
by pure grader functions; the runner is extended to record the final world-state on
the `Trajectory` so the grader can read it without recomputation; the
`forbidden_action` and `step_limit_exceeded` failure categories (already declared but
never emitted) are wired into the taxonomy; and the golden conformance suite is
extended with hand-verified cases proving each new spec, path-independence, and
`AllOf` conjunction semantics. The change is strictly additive: every existing v1
grading behavior, golden case, and the full 130-test suite stay green.

## Acceptance criteria

Each criterion is independently verifiable by a test or a command.

1. **Union extension.** `tasks/schema.py` defines `FinalStateSpec`,
   `TrajectorySpec`, and `AllOf` as `@dataclass(frozen=True, kw_only=True)` with the
   exact field shapes and `type` discriminators from design §4.3
   (`"final_state"`, `"trajectory"`, `"all_of"`), and the constraint data variants
   `StateEquals`/`StateContains` (`StateConstraint` union) and
   `NoToolCall`/`OnlyModifies`/`MaxToolCalls` (`TrajectoryConstraint` union). The
   public `VerificationSpec` alias becomes
   `OutputMatchSpec | ToolCallMatchSpec | FinalStateSpec | TrajectorySpec | AllOf`.
   `AllOf.specs` is typed against `VerificationSpec` (forward reference) so it nests
   recursively. No behavior lives on any record.
2. **Final-state threading.** `records/trajectory.py` gains
   `final_state: Mapping[str, Any] | None = None` (optional, defaulted) on
   `Trajectory`; `runners/loop.py` records the post-loop world-state into it; every
   existing `Trajectory(...)` construction site (10 sites across src + tests) still
   compiles unchanged because the field is defaulted. `records/serialize.py`
   round-trips `final_state` (omitted/`None` ⇒ absent or null in the dict, present ⇒
   serialized verbatim).
3. **Pure state grader.** A new pure module (e.g. `graders/state.py`) interprets
   `FinalStateSpec` against `(initial_state, trajectory.final_state)`. A dot-path
   walker (`"tickets.T-1.status"`) resolves over nested mappings; a missing key or a
   non-mapping intermediate yields a sentinel that **fails the constraint and never
   raises**. `StateEquals` passes iff the resolved value `==` the expected value;
   `StateContains` passes iff the resolved value is a container and the expected
   value is a member, and fails (never raises) on a missing path or non-container.
   A failed state constraint carries `failure_reason=None` (a plain assertion miss,
   not a policy breach); see criterion 9 for the full reason mapping.
4. **Pure trajectory grader.** A new pure module (e.g. `graders/policy.py`)
   interprets `TrajectorySpec` against `(initial_state, trajectory)`. `NoToolCall`
   fails with `failure_reason="forbidden_action"` if any `ToolCallTurn` contains a
   call whose `name` matches. `MaxToolCalls(n)` fails with
   `failure_reason="step_limit_exceeded"` if the total number of tool calls across
   all `ToolCallTurn`s exceeds `n`. `OnlyModifies(paths)` diffs `initial_state`
   against `trajectory.final_state`, computes the set of changed leaf paths, and
   fails with `failure_reason="forbidden_action"` if any changed path is not covered
   by (equal to or prefixed by) a declared path.
   ~~"prefixed by" (raw string)~~ — corrected by grill: prefix coverage is
   **dot-segment-aware**, not raw-string — a declared `tickets.T-1` covers
   `tickets.T-1.status` but NOT `tickets.T-10.status` (see ADR-0002, Q3 below).
5. **AllOf conjunction.** A pure interpreter evaluates `AllOf.specs` in declared
   order, recursing through `grade_trajectory`. `passed` is the logical AND of all
   sub-results. On failure, `failure_reason` is taken from the **first failing
   sub-spec in declared order**; `evidence` carries an ordered list of every
   sub-result (passed and failed) so the audit trail is complete. `score` is
   all-or-nothing (`1.0` iff passed else `0.0`).
6. **Dispatch wiring.** `graders/dispatch.py::grade_trajectory` gains an optional
   `initial_state: Mapping[str, Any] | None = None` parameter and `isinstance`
   branches for `FinalStateSpec`, `TrajectorySpec`, and `AllOf`. The existing
   `OutputMatchSpec`/`ToolCallMatchSpec` branches are byte-for-byte unchanged and
   ignore `initial_state`. The `raise ValueError(f"unsupported verification spec…")`
   fallthrough remains for genuinely unknown specs (e.g. `LlmJudgeSpec`, item 003).
   The `AllOf` branch recurses through `grade_trajectory` threading **both** the
   existing required `registry` **and** `initial_state` to every sub-spec, so a
   `ToolCallMatchSpec` nested inside an `AllOf` still receives its `registry` (see
   Q8 below — `registry` stays required, `initial_state` is the only new param).
7. **Runner pass-through.** `runners/multi_run.py` passes
   `initial_state=task.initial_state` into `grade_trajectory`. No other runner
   behavior changes.
8. **JSONL parsing.** `tasks/parse.py::verification_from_dict` parses `final_state`,
   `trajectory`, and `all_of` discriminators into the new records, including the
   constraint sub-dicts (`state_equals`, `state_contains`, `no_tool_call`,
   `only_modifies`, `max_tool_calls`) and recursive `all_of.specs`. Unknown
   constraint types and unknown spec types raise `ValueError` (consistent with the
   existing `match`-mode and `split` validation style). Round-trip
   (`dict → spec → grade`) is exercised by the golden suite.
9. **Failure-category mapping is exhaustive and deterministic.** The only categories
   this item introduces are `forbidden_action` (from `NoToolCall`, `OnlyModifies`)
   and `step_limit_exceeded` (from `MaxToolCalls`). `FinalStateSpec` constraint
   misses (`StateEquals`/`StateContains`) carry `failure_reason=None` (a plain
   outcome assertion, like a failed `OutputMatchSpec`), with the mismatch captured
   in `evidence`. No new member is added to the `FailureCategory` literal (both are
   already declared in `records/grade.py`).
10. **Golden conformance extension.** `tests/test_golden_conformance.py` is extended:
    the suite-size assertion is bumped from 11 to the new total, the harness threads
    `initial_state=case.get("initial_state")` into `grade_trajectory` (v1 cases that
    omit it are unaffected), and new hand-verified JSON cases are added covering at
    minimum: (a) `FinalStateSpec` state-equals success, (b) `FinalStateSpec`
    state-equals failure, (c) `FinalStateSpec` over a **missing path** (fails, does
    not crash), (d) `StateContains` success and failure, (e) `NoToolCall`
    forbidden-action breach, (f) `MaxToolCalls` step-limit breach, (g)
    `OnlyModifies` breach (a path outside the allowed prefix changed), (h)
    **path-independence**: two cases with *different* valid tool paths reaching the
    same final state both pass the same `FinalStateSpec`, (i) `AllOf` all-pass
    success, and (j) `AllOf` conjunction where two sub-specs fail and the recorded
    `failure_reason` is the first failing sub-spec's, with `evidence` listing all
    sub-results. Each case states its hand-verified expected `passed` and
    `failure_reason`.
11. **Backward compatibility.** All 11 existing golden cases pass unchanged, and the
    full suite stays green: ~~`PYTHONPATH=src python -m pytest` reports ≥130 passing~~
    — corrected by grill: the project's canonical gate (MASTER-PLAN) is
    `uv run pytest -q`, `uv run ruff check .`, `uv run ruff format --check .`; the
    current suite is **exactly 130** tests, so the new golden cases and pure-unit
    tests push the total **above 130** with no regressions; `ruff check` and
    `ruff format --check` are clean.

## Non-goals

- **`LlmJudgeSpec` and the calibration harness** — item 003. The union extension must
  not paint it into a corner (the recursive `AllOf` and the optional-`initial_state`
  dispatch signature already leave room for a judge branch and for deterministic +
  judge coexistence via `AllOf`), but no judge code, prompt, or κ machinery ships here.
- **`ExecutionSpec`** — Weeks 5-6 (code-repair). Not added to the union by this item.
- **`ScriptedUser` / `ask_user` multi-turn** — Weeks 9-10; explicitly OUT per
  MASTER-SPEC.
- **New workspace tools or world-state shape changes** (e.g. `send_email`, `emails`,
  `accounts`) — that surface expansion is item 002. This item grades against the
  existing `tickets`/`docs` shape plus whatever `initial_state` a task carries; it
  does not add tools.
- **The v2 dataset itself** (`workspace_tool_use_v2.jsonl`) — item 002. This item
  ships the grader and parser the dataset will rely on, proven by golden cases, not
  by dataset rows.
- **Changing v1 grading semantics** — `OutputMatchSpec`/`ToolCallMatchSpec` graders,
  their failure taxonomy, and the canonicalization pipeline are untouched.
- **Metrics/experiments/reports changes** — `pass^k`, CIs, and report rendering are
  unaffected; they consume `GradeResult` whose shape is unchanged.

## Constraints

- **Public-API stability.** The change is purely additive. `VerificationSpec` widens
  (a non-breaking superset); `Trajectory` and `grade_trajectory` each gain one
  optional, defaulted member/parameter so no existing call site changes. No field is
  removed or renamed. `GradeResult` and `FailureCategory` are unchanged (the two new
  categories were already declared).
- **Purity / FP discipline.** All grader and parser functions are pure: deterministic,
  no I/O, no logging, no mutation of arguments. State diffing builds new sets/tuples
  via comprehensions; no `push`/`pop`/in-place edits. Records stay frozen
  (`@dataclass(frozen=True, kw_only=True)`) and serializable — behavior lives only in
  functions. New modules stay small and single-purpose (state interpreter, policy
  interpreter, composite interpreter each ≤ ~120 lines), consistent with the existing
  `graders/` layout.
- **Determinism / robustness.** Grading is a pure function of
  `(spec, initial_state, trajectory)`. Missing dot-paths, non-mapping intermediates,
  and non-container `StateContains` targets must **fail the constraint, never raise**
  — a malformed expectation degrades to a clean grade miss, never a harness crash.
  This is the executable form of "distinguish agent failures from harness failures."
- **Performance.** Grading is linear in trajectory length and state size; no
  per-call replay of the world (final state is read off the trajectory, not
  recomputed). Whole suite must keep running in well under a second (current full run
  ≈ 0.4 s).
- **Dependencies.** No new runtime dependencies. State/policy graders use only the
  stdlib; `jsonschema` is already vendored for arg validation and is not needed here.
- **Security.** No new I/O surface, no eval/exec, no untrusted-input execution.
  Dot-paths are split on `.` and used only as mapping keys (never as attribute access
  or code), so a crafted path string cannot reach beyond the state mapping.
- **TDD.** Red-green-refactor throughout: the golden conformance cases and pure-unit
  tests are the oracle and are written before the interpreters they verify.

## Open questions resolved during brainstorming (with rationale)

1. **Where is the final world-state recorded?** → **On `Trajectory`, as an optional
   defaulted `final_state` field.** Considered (a) recording on `Trajectory`,
   (b) recomputing in the grader by replaying `apply` over tool-result turns, and
   (c) passing state as a separate grader argument threaded from the runner.
   (b) is rejected: it duplicates runner logic inside the pure core and risks the
   grader and the world disagreeing on outcomes — design §5 explicitly requires the
   world and grader to agree, and replay from partial turn data is fragile. (c) works
   for the live path but breaks the golden suite's self-contained
   `{verification, trajectory}` replay artifact unless a sibling `final_state` is also
   added — at which point (a) is strictly cleaner because the trajectory stays the
   single replay artifact. The runner already holds the state local; recording it is a
   one-line, fully backward-compatible addition.

2. **Dot-path semantics and missing-path grading.** → **Walk nested mappings
   key-by-key; missing key or non-mapping intermediate yields a `_MISSING` sentinel
   that fails the constraint, never raises.** This satisfies the explicit MASTER-SPEC
   directive ("missing paths must FAIL the constraint, never crash") and keeps the
   grader a total function. `StateContains` additionally fails (not raises) when the
   resolved value is not a container.

3. **`OnlyModifies` "modified" computation and granularity.** → **Diff
   `initial_state` (from `Task.initial_state`) against `trajectory.final_state`,
   compute the set of changed *leaf* dot-paths (added, removed, or value-changed), and
   permit a change iff some declared path is a prefix of (or equal to) the changed
   path.** Leaf-path granularity with prefix-coverage matches the design's example
   `OnlyModifies(paths=("tickets.T-1",))` — meant to permit any change *under*
   `tickets.T-1` while forbidding edits elsewhere. Prefix semantics (not exact-path)
   are required for the example to behave as intended.

4. **`AllOf` `failure_reason` precedence.** → **First failing sub-spec in declared
   order wins; `evidence` carries all sub-results.** A deterministic, author-visible
   rule (declared order is the author's stated priority); "first failure" is the least
   surprising and matches how short-circuit conjunctions are usually read, while still
   evaluating and recording *every* sub-result so the taxonomy and audit trail see the
   full picture (we evaluate all sub-specs rather than short-circuiting, precisely so
   evidence is complete).

5. **Score semantics for composite specs.** → **All-or-nothing: `score = 1.0` iff
   `passed` else `0.0`; `passed` stays boolean.** Rationale: the headline metric is
   `pass^k` task-level reliability (design §4.6, §7), which consumes the boolean
   `passed`; a fractional composite score would have no consumer and would invite
   "partial credit" interpretations that muddy the reliability estimand. Keeping
   `score` a redundant boolean-mirror is consistent with every existing grader
   (`grade_exact_match`, `ast_tool_match` both emit `1.0`/`0.0`) and avoids a
   gratuitous semantic divergence. Fractional scoring, if ever wanted, is a separate
   future decision and is YAGNI here.

6. **Does the union extension corner `LlmJudgeSpec` (item 003)?** → **No.** The
   recursive `AllOf` already supports deterministic + judge coexistence on one task
   (design §6 step 5: the deterministic part always runs, the judge handles the
   subjective residue), and the optional-`initial_state` dispatch signature leaves the
   judge branch free to ignore state. No commitment made here blocks a clean
   `LlmJudgeSpec` branch later.

7. **What failure category do `FinalStateSpec` misses carry?** → **`None`** (a plain
   outcome assertion, like a failed `OutputMatchSpec`), with the mismatch in
   `evidence`. `forbidden_action`/`step_limit_exceeded` are reserved for *policy*
   breaches (`TrajectorySpec`), which is what the design's taxonomy names them for; a
   state value simply not matching is a missed expectation, not a forbidden action.
   This keeps the taxonomy semantically honest and avoids overloading the two new
   categories.

### Not resolvable from MASTER-SPEC alone

None. Every open question listed in the orchestrator brief was resolvable from the
locked design doc (§4.3–§4.6, §5, §6, §14) plus the current checkout; all are
resolved above with code-grounded rationale. The auto-resolved recommendations stand
as the design of record for implementation.

## Resolved decisions

Grill pass (autonomous, recommendations auto-accepted). Each pairs a question with
the accepted answer, a one-line rationale, and its doc impact. Questions are
code- and design-grounded; nothing here contradicts the locked design or current
checkout.

- **Q1. Where is the final world-state recorded?**
  A: On `Trajectory` as an optional defaulted `final_state` field; the runner
  populates it from its post-loop `state` local. Considered recompute-by-replay and
  pass-as-separate-arg.
  Rationale: keeps the trajectory the single self-contained replay artifact and
  guarantees world/grader agreement (design §5) without duplicating runner logic.
  Doc impact: ADR-0001; CONTEXT term `final_state`.

- **Q2. Dot-path walk and missing-path grading.**
  A: Walk nested mappings segment-by-segment; a missing key or non-mapping
  intermediate yields a `_MISSING` sentinel that **fails the constraint, never
  raises**. `StateContains` additionally fails (not raises) on a non-container
  resolved value.
  Rationale: MASTER-SPEC directive ("missing paths must FAIL, never crash"); keeps
  the grader a total function — the executable form of "distinguish agent failures
  from harness failures".
  Doc impact: none (matches spec criteria 3/9 and the Constraints/robustness
  section verbatim).

- **Q3. `OnlyModifies` "modified" set and prefix granularity.**
  A: Diff `initial_state` vs `final_state` into changed *leaf* dot-paths; permit a
  change iff a declared path equals or is a **dot-segment prefix** of the changed
  path. A declared `tickets.T-1` covers `tickets.T-1.status` but NOT
  `tickets.T-10.status`. Considered exact-path matching.
  Rationale: matches the design §4.3 example `OnlyModifies(paths=("tickets.T-1",))`,
  which names a subtree the agent may touch; raw-string prefixing would wrongly let
  `tickets.T-10` pass under a `tickets.T-1` allowance.
  Doc impact: ADR-0002; strike on criterion 4.

- **Q4. `AllOf` `failure_reason` precedence and short-circuit.**
  A: Evaluate **every** sub-spec (no short-circuit); `passed` is the AND; report the
  **first failing** sub-spec's `failure_reason`; `evidence` carries the ordered list
  of all sub-results. Considered short-circuit-on-first-failure.
  Rationale: the JD#4 failure taxonomy and audit trail need every co-occurring
  breach visible; first-failure keeps the headline category deterministic and reads
  as declared-order priority.
  Doc impact: ADR-0003; CONTEXT term `AllOf`.

- **Q5. Score semantics for composite/state/policy specs.**
  A: All-or-nothing — `score = 1.0` iff `passed` else `0.0`; `passed` stays boolean.
  Rationale: the headline metric is `pass^k` task-level reliability (design
  §4.6/§7), which consumes the boolean; a fractional composite score has no consumer
  and would invite partial-credit ambiguity. Mirrors every existing grader
  (`grade_exact_match`, `ast_tool_match` emit `1.0`/`0.0`). YAGNI for fractional.
  Doc impact: none (consistent with §4.5 and existing graders).

- **Q6. Does the union extension corner `LlmJudgeSpec` (item 003)?**
  A: No. Recursive `AllOf` already supports deterministic + judge coexistence on one
  task (design §6 step 5); the optional-`initial_state` dispatch signature lets a
  future judge branch ignore state.
  Rationale: no commitment here blocks a clean `LlmJudgeSpec` branch; the
  `raise ValueError` fallthrough still guards genuinely unknown specs.
  Doc impact: none.

- **Q7. What `failure_reason` do `FinalStateSpec` misses carry?**
  A: `None` — a plain outcome assertion, like a failed `OutputMatchSpec`, with the
  mismatch in `evidence`. `forbidden_action`/`step_limit_exceeded` are reserved for
  *policy* breaches (`TrajectorySpec`).
  Rationale: keeps the taxonomy semantically honest; a value not matching is a
  missed expectation, not a forbidden action. No new `FailureCategory` member is
  added (both are already declared in `records/grade.py`).
  Doc impact: CONTEXT terms `FailureCategory`, `forbidden_action`,
  `step_limit_exceeded`.

- **Q8. Does `AllOf` recursion break the required `registry` argument?**
  A: No, but it must be threaded. `grade_trajectory`'s `registry` stays a
  **required** parameter (current signature; a nested `ToolCallMatchSpec` needs it);
  `initial_state` is the **only** new (optional, defaulted) parameter. The `AllOf`
  branch passes **both** `registry` and `initial_state` to every recursive
  sub-call.
  Rationale: grounded in `graders/dispatch.py` and `graders/tool_call.py` —
  `grade_tool_call_match` requires `registry` for schema-violation detection;
  dropping or defaulting it would regress v1 grading inside a composite.
  Doc impact: clarification added to criterion 6.

- **Q9. Do state/policy graders need `registry`?**
  A: No. `graders/state.py` and `graders/policy.py` are pure functions of
  `(spec, initial_state, trajectory)` and never touch the tool registry; only the
  `ToolCallMatchSpec` branch (and `AllOf` threading it) consumes `registry`.
  Rationale: state/policy grade world-state and call-name/count, none of which
  require tool schemas; keeps the new modules minimal and the dependency explicit.
  Doc impact: none.

- **Q10. Should state-value comparison canonicalize like tool-call args do?**
  A: No. `StateEquals` uses plain `==`; `StateContains` uses plain membership. The
  `graders/canonical.py` pipeline (key-order / sequence-type normalization) is for
  comparing *tool-call arguments* against `ExpectedToolCall`, not world-state.
  Rationale: world-state is produced by the deterministic `apply` and compared
  against an author-written expected value; introducing canonicalization here would
  silently broaden equality and is unrequested by the design. Type coercion stays a
  mismatch, consistent with the never-repair principle (design §6, decision 7).
  Doc impact: none.

- **Q11. Canonical verification command and current test count.**
  A: `uv run pytest -q` / `uv run ruff check .` / `uv run ruff format --check .`
  (MASTER-PLAN), not `PYTHONPATH=src python -m pytest`. Current suite is **exactly
  130** tests; new golden + unit tests push the total above 130 with zero
  regressions and all 11 existing golden cases unchanged.
  Rationale: grounded in `docs/2026-06-10-dataset-grader-quality/MASTER-PLAN.md`
  and a live `--collect-only` count of 130.
  Doc impact: strike on criterion 11.

- **Q12. Does serialization need a new top-level `final_state` round-trip path?**
  A: Yes, and only in `records/serialize.py::trajectory_to_dict`/`_from_dict`:
  emit `final_state` verbatim when present, omit-or-null when `None`. No new
  serializer module; `tasks/parse.py` parses the *spec* discriminators
  (`final_state`/`trajectory`/`all_of` + constraint sub-dicts), which is a distinct
  concern from trajectory serialization.
  Rationale: grounded in the two distinct round-trip surfaces — `serialize.py`
  (records, incl. `Trajectory`) vs `tasks/parse.py` (`VerificationSpec`). Criterion
  2 covers the former, criterion 8 the latter; they must not be conflated.
  Doc impact: none (clarifies criteria 2 and 8 are separate surfaces).
