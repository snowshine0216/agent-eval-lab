# Final world-state is recorded on the Trajectory, not recomputed or passed alongside

The state and policy graders (`FinalStateSpec`, `TrajectorySpec`) need the
world-state a run reached. We record it as an optional, defaulted
`final_state: Mapping[str, Any] | None` field on the `Trajectory` record, which
the runner populates from its post-loop `state` local.

## Considered Options

- **(a) Record on `Trajectory`** (chosen). One backward-compatible line in the
  runner; the trajectory stays the single self-contained replay artifact that
  the golden conformance suite serializes and grades.
- **(b) Recompute in the grader** by replaying `apply` over tool-result turns.
  Rejected: it duplicates runner logic inside the pure core and risks the world
  and the grader disagreeing on the outcome — design §5 explicitly requires them
  to agree, and replay from partial turn data is fragile.
- **(c) Pass state as a separate grader argument** threaded from the runner.
  Works for the live path but breaks the golden suite's self-contained
  `{verification, trajectory}` artifact unless a sibling `final_state` is added
  anyway — at which point (a) is strictly cleaner.

## Consequences

`Trajectory` gains one optional defaulted field, so all 10 existing construction
sites compile unchanged and serialization round-trips `final_state` as
absent/null when unset. The grader is a pure function of
`(spec, initial_state, trajectory)` with no replay, keeping grading linear and
the world/grader agreement guaranteed by construction.
