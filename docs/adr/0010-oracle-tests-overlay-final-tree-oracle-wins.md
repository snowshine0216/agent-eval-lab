# Oracle tests overlay the final tree; the oracle wins exact-path collisions

Execution grading (item 002) must combine a task's held-out oracle tests with the
trajectory's final file tree before running pytest. The overlay is **oracle-wins**:
on an exact-path collision the oracle file replaces the agent's, and the displaced
agent path is recorded as evidence on the `ExecutionVerdict` — displacement is never
itself a fail. A canonical-prefix collision (identical NFC+casefold form, different
spelling) cannot be silently resolved and becomes a structured
`ExecutionError(kind="tree_collision")` — a graded non-pass with
`failure_reason=None`, never a harness crash.

## Considered Options

- **Oracle-wins with displaced-path evidence** (chosen). Closes the
  agent-overwrites-the-oracle reward hack while not punishing the agent for paths it
  cannot know exist; the prefix-collision case stays a gradeable record item 004's
  task/agent/harness classifier can reach.
- **Agent-wins.** Rejected: the agent could pre-write trivial tests at the oracle
  path and mask the oracle entirely — a direct reward-hack vector.
- **Error on any exact-path collision.** Rejected: oracle paths are hidden by
  design, so the agent can legally write them; failing the run punishes unknowable
  collisions.

## Consequences

The pure overlay detects prefix collisions *before* materialization, reusing
code-world's single collision predicate (one implementation; `pytest_edge`'s
materializer guard stays defense-in-depth only). Overlay semantics are baked into
recorded verdicts and golden expectations, so changing them later invalidates the
run's artifacts — this is fixed for the slice.

## Residual trust boundary

The file-level attack surface is closed by reserving `.junit.xml`,
`sitecustomize.py`, and `usercustomize.py` in both the pure tool layer and the
materializer guard. The remaining exposure is import-time code in agent-authored
modules: the oracle suite imports them in-process, so a graded module can run
arbitrary code at import. v1 accepts this — the dataset is curated and the item 003
rubric screens for exploitable tasks; full per-test process isolation is out of scope.
