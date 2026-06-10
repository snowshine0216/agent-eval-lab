# Agent Eval Lab

A reproducible agent-evaluation harness: tasks carry a tagged-union
`VerificationSpec`; an effectful runner produces a `Trajectory`; pure tiered
graders interpret the spec into a `GradeResult`; pure metrics aggregate runs
into reliability and cost numbers. Functional core, imperative shell.

## Language

### Verification & grading

**VerificationSpec**:
The tagged union describing how a task is graded. Each variant
(`OutputMatchSpec`, `ToolCallMatchSpec`, `FinalStateSpec`, `TrajectorySpec`,
`AllOf`, and later `ExecutionSpec`/`LlmJudgeSpec`) carries only the fields that
variant needs, so illegal states are unrepresentable. It is inert serializable
data — behavior lives in the pure graders, never on the record.
_Avoid_: "grader config", "scorer spec", "rubric" (the rubric is a judge
artifact, distinct).

**Constraint**:
A serializable data variant *inside* a `FinalStateSpec` or `TrajectorySpec` that
a pure interpreter evaluates. State constraints (`StateEquals`, `StateContains`)
assert outcome; trajectory constraints (`NoToolCall`, `OnlyModifies`,
`MaxToolCalls`) assert policy. A constraint is not itself a `VerificationSpec`.
_Avoid_: "rule", "check", "assertion" (these blur constraint vs spec vs grader).

**Outcome verification**:
Grading the *world-state a run reached*, independent of which tool path reached
it (`FinalStateSpec`). Many valid paths can pass the same final-state check.
_Avoid_: "result check", "state assertion" (informal).

**Policy verification**:
Grading the *path a run took* for forbidden side-effects, even when the outcome
is correct (`TrajectorySpec`). The complement of outcome verification: outcome
says "did it get there", policy says "did it harm nothing on the way".
_Avoid_: "side-effect check", "trajectory grading" (overloaded — `TrajectorySpec`
grades policy, not the whole trajectory's correctness).

**Path-independence**:
The property that `FinalStateSpec` grades the reached world-state, not the
sequence of tool calls — so two runs taking different valid tool paths to the
same `final_state` grade identically. Path-independence is *outcome only*;
policy is reintroduced deliberately via `TrajectorySpec` so path-independence
never means "ignore harmful actions".
_Avoid_: "order-independent" (that's the `multiset` match mode of
`ToolCallMatchSpec`, a different concept).

**final_state**:
The post-loop world-state snapshot the runner records on the `Trajectory`. It is
the single artifact the state/policy graders read; they never replay the world
to recompute it. `None` when no state-graded run produced one. Distinct from
`Task.initial_state` (the pre-run world the runner seeds and the diff baseline).
_Avoid_: "world", "final world" (ambiguous with the runner's live `state` local).

**FailureCategory**:
The closed literal taxonomy a `GradeResult` carries to explain *why* a run
failed (`malformed_call`, `schema_violation`, `wrong_tool`, …,
`forbidden_action`, `step_limit_exceeded`). `forbidden_action` and
`step_limit_exceeded` name *policy* breaches only. An outcome assertion that
simply does not match (a `StateEquals`/`StateContains`/`OutputMatchSpec` miss)
carries `failure_reason=None` — it is a missed expectation, not a forbidden
action.
_Avoid_: adding a category for plain assertion misses; `None` is the category
for "the answer was wrong, no policy was violated".

**forbidden_action**:
The `FailureCategory` for a *policy* breach where a run did something it must not:
a `NoToolCall`-named tool was called, or a state path outside the `OnlyModifies`
allowlist changed. Not used for a value simply being wrong.

**step_limit_exceeded**:
The `FailureCategory` for a `MaxToolCalls(n)` breach: the total number of tool
calls across the trajectory exceeded `n`. Counts *calls* (each entry of every
`ToolCallTurn.tool_calls`), not turns.

**AllOf**:
The composite `VerificationSpec` variant: a conjunction of nested specs, all of
which must pass. It evaluates *every* sub-spec (no short-circuit) so the audit
trail is complete, ANDs their `passed`, and reports the `failure_reason` of the
*first* failing sub-spec in declared order. Recursive: an `AllOf` may nest
another `AllOf`.
_Avoid_: "compound spec", "and-spec".

### Existing terms (for reference, defined by the locked design)

**Task**:
A single evaluation unit: id, capability, input (messages + available tool
schemas), a `VerificationSpec`, metadata, and an optional `initial_state`.

**Trajectory**:
The record a single run emits: the turns, token usage, latency, `run_index`,
stop reason, and (when state-graded) `final_state`. Immutable; replayable from
`initial_state`.

**GradeResult**:
The pure grader's verdict over one trajectory: `grader_id`, `passed`, `score`,
`evidence` (the audit trail of what the grader saw), and `failure_reason`.

### Dataset engineering

**Distractor tool**:
A registered, schema-valid tool whose name/behavior deliberately overlaps a
correct tool so that picking it is a *gradeable wrong path*, never a correct one
(`archive_ticket` vs `update_ticket`, `find_account` vs `get_account`,
`draft_email` vs `send_email`). A distractor never appears in any task's
`ExpectedToolCall`, and its signature state (`status:"archived"`,
`emails.*.state:"draft"`) is never asserted as a *passing* outcome — only forbidden
(`NoToolCall`) or used as the wrong-path state a correct `FinalStateSpec`
distinguishes against. The conformance test enforces "distractor never expected".
_Avoid_: "filler tool", "decoy" (a distractor must be gradeable, not noise).

**Difficulty knob**:
A named lever from a closed vocabulary (`multi_step_depth`, `derived_argument`,
`distractor_count`, `argument_complexity`, `layered_constraint`) that a task
records in `metadata.difficulty_knob` to declare *the one thing* that makes it
hard. Long-horizon is a *property* (chain depth via `multi_step_depth` +
`max_steps`), not a knob of its own.
_Avoid_: "hardness", "difficulty level" (the *tier* is the level; the knob is the
mechanism).

**Tier**:
The coarse hardness band of a task (`T1` sanity, `T2` moderate, `T3` hard, `T4`
adversarial), carrying a per-tier *expected-failure rationale*. Orthogonal to
`capability` (the skill isolated) and to `difficulty_knob` (the mechanism). The
hard tiers (T3+T4) are the majority of v2 by directive.
_Avoid_: "level", "grade" (grade is the run verdict, `GradeResult`).

**State-dependent chain**:
A multi-call task where at least one call's arguments are *unknowable* from the
prompt or `initial_state` alone — they derive from a prior call's *result* (a
minted id, or an id/field only surfaced by `list_tickets`/`find_account`). The
discriminating opposite of a *rote chain* (independent calls whose args are all
present up front). The conformance test enforces a structural proxy: a
`multi_step_depth`/`derived_argument` task must reference at least one entity not
present in `initial_state` or the prompt.
_Avoid_: "long chain", "multi-step" (length alone does not imply dependence).

**provenance**:
Closed `metadata.provenance` vocabulary recording how a task was produced;
counted in the dataset card (§9). `hand_written` is canonical for human-authored
tasks (established by v1; v2 reuses it). A future generator adds one new value
(`generated`), not a synonym.
_Avoid_: "hand_authored", "hand-authored", "manual" (synonyms fracture the count).

**version (dataset)**:
The `metadata.version` string naming the *dataset/world generation* a task belongs
to (`"1"` for v1, `"2"` for v2). Co-varies with `world_template_id`
(`workspace-v1`/`workspace-v2`). It is the world-revision counter, NOT a per-row
append-only revision number.
_Avoid_: "schema version", "row version" (it versions the world+task-set, not the
record schema).

**world_template_id**:
The `metadata.world_template_id` naming the parametrized world a task is built on
(`workspace-v1`, `workspace-v2`). It is the §7 *isolation boundary* for the
Weeks 9-10 train/dev/held-out splits — a template (and its seed family) belongs to
exactly one partition. Carried on every task from day one so splits never need
retrofitting.
_Avoid_: "world id", "scenario id" (it names the *template*, not an instance).

**max_steps (task hint)**:
The optional `metadata.max_steps` a task declares as the loop-iteration budget its
intended dependent chain needs, floored at `dependent_calls + 2` (headroom for the
model's read/confirm turns). It is *data*; threading it through the runner is item
004's contract. Distinct from the runner's run-level `max_steps` argument (today a
global CLI default of 6).
_Avoid_: "step limit", "max turns" (`step_limit_exceeded` is the policy
`FailureCategory`; `max_steps` here is the per-task budget hint).

**review (task)**:
The `metadata.review` field (`"passed:<rubric-version>"`) that rides each
append-only row as its *machine-checkable, frozen* proof the task passed the
authoring rubric. The `review-ledger.md` is the *human-readable, regenerable* audit
view keyed by task id; the field, not the ledger, is the source of truth for review
coverage.
_Avoid_: "rubric" alone (the *rubric* is the author's task-validity checklist —
distinct from the item-003 judge rubric, a known naming hazard).

## Example dialogue

> **Dev:** The task says "close ticket T-1 and don't email anyone". Is that one
> spec or two?
>
> **Domain expert:** One composite. An `AllOf` of two specs. The
> `FinalStateSpec` is the *outcome* check — `StateEquals` on
> `tickets.T-1.status == "closed"`. The `TrajectorySpec` is the *policy* check —
> `NoToolCall("send_email")` plus maybe `OnlyModifies(("tickets.T-1",))`.
>
> **Dev:** If the agent closes the ticket by a weird three-tool path, does it
> still pass the outcome check?
>
> **Domain expert:** Yes — that's path-independence. `FinalStateSpec` reads the
> reached `final_state`, not the path. But if it sent an email along the way the
> *policy* check fails with `forbidden_action`, even though the outcome was
> right. Path-independence never means "ignore harm".
>
> **Dev:** And if the ticket just ended up `"open"` instead of `"closed"`?
>
> **Domain expert:** That's an outcome miss, not a policy breach — the
> `StateEquals` fails with `failure_reason=None`. We reserve `forbidden_action`
> and `step_limit_exceeded` for things the agent must not *do*.
>
> **Dev:** For v2 I wrote a T4 task that creates eight tickets in one go. Eight
> calls — that's a long horizon, right?
>
> **Domain expert:** Eight *independent* creates is a **rote chain**, not a
> **state-dependent chain**. Every title is in the prompt; nothing derives from a
> prior **result**. Length isn't the **difficulty knob** — `multi_step_depth`
> means step N's args are unknowable until step N-1 returns. The conformance test
> would reject it: a `multi_step_depth` task must reference an id that isn't in
> `initial_state` or the prompt, like the ticket `list_tickets` says is the oldest.
>
> **Dev:** It uses `draft_email` to notify the owner. The `FinalStateSpec` checks
> `emails.e-1.state == "draft"`. Pass?
>
> **Domain expert:** No — `draft_email` is a **distractor**. "Notify" means
> *send*. A correct task asserts `emails.e-1.state == "sent"` and the conformance
> check forbids a distractor's signature state (`"draft"`, `"archived"`) ever being
> a *passing* outcome. The distractor only shows up as the wrong path a correct
> spec discriminates against, or inside a `NoToolCall`.
>
> **Dev:** And the budget — `max_steps`?
>
> **Domain expert:** That's the per-task `metadata.max_steps`, floored at dependent
> calls + 2. It's *data*; the runner still takes a global default of 6 today, so
> item 004 must thread the per-task value or every T3/T4 task starves at the step
> limit. We ship the contract now and prove it with the conformance floor.
