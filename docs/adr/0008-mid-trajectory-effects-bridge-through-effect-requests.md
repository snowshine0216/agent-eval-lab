# Mid-trajectory effects bridge through effect-requests fulfilled by the runner loop

Code-world's `run_tests` needs subprocess I/O, but `apply` is pure — and
ADR-0005's edge-precompute cannot work mid-trajectory, because the file tree to
execute is unknowable before the run reaches that turn. We generalize the rule
instead of breaking it: pure `apply` returns a frozen, serializable
`ExecutionRequest` (a file-tree snapshot, nothing else) in the outcome position
— the return type widens explicitly to
`tuple[State, ToolOutcome | ExecutionRequest]` — and the runner loop, the
existing I/O boundary, fulfills it through an executor callable matched on the
request *type* (never the tool-name string), recording a `ToolResultTurn` with
`ToolSuccess(result=<serialized ExecutionResult>)`.

## Considered Options

- **Effect-request, loop fulfills** (chosen). The effectful input is still
  produced at the edge and threaded as immutable data — ADR-0005's rule,
  generalized from pre-run precompute to in-loop fulfillment. Argument
  validation stays in `apply` beside every other tool; the trajectory carries
  only plain recorded data, so `records/turns.py` and the serialization layer
  are untouched.
- **Name-based loop interception** (loop special-cases `name == "run_tests"`).
  Rejected: couples the loop to world vocabulary, splits validation from
  `apply`, and breaks silently when a world renames a tool.
- **Real-filesystem tools** (tools perform I/O directly). Rejected: destroys
  purity, `final_state`, and ADR-0001 replayability in one move.
- **ADR-0005-style literal precompute.** Rejected: impossible — the
  mid-trajectory tree does not exist before the run.

## Consequences

The loop gains two additive defaulted parameters (world `apply`, executor); all
existing workspace-world runner tests pass unchanged. A fulfilled request is
**always** recorded as `ToolSuccess`, whatever the suite status — failing tests
are a *successful tool call*; `ToolFailure` stays reserved for pure validation
(bad path, schema violation, unknown tool), keeping the item-004 failure
taxonomy unconfounded. An `ExecutionRequest` reaching a loop with no executor
is a harness misconfiguration and raises `RuntimeError` (mirroring
`workspace.apply`'s registered-but-unimplemented guard) — never a `ToolFailure`
shown to the agent. Replay semantics survive the effectful tool: recorded
results are data, like recorded model replies; replaying a trajectory
recomputes `final_state` through pure `apply` (`run_tests` is state-identity)
and never re-executes. Item 002's `ExecutionSpec` grader reads the recorded
results, completing the succession ADR-0005 named. (Clarified by item 002 /
ADR-0011: "the recorded results" are the `ExecutionVerdict`s the oracle edge
precomputes post-trajectory and threads in as data — not the agent's mid-run
`run_tests` records, which cover only the visible tests.)
