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
