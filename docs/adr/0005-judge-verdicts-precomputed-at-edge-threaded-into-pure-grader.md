# Judge verdicts are pre-computed at the edge and threaded into the pure grader

A `LlmJudgeSpec` needs a provider call, but `grade_trajectory` is pure and must
stay pure. We resolve this the same way the codebase already resolves
`final_state`: the **edge pre-computes the effectful input** (here a
`JudgeVerdict` per reachable `LlmJudgeSpec`, via `runners/judge_edge.run_judge`),
and the **pure grader only reads it** from an immutable
`verdicts: Mapping[str, JudgeVerdict | JudgeError]` keyed by the pure prompt hash,
threaded unchanged through `grade_trajectory` and `grade_all_of` (so a judge leg
can sit inside an `AllOf` beside deterministic legs). The verdict map is built by
walking the spec tree with a pure `collect_judge_specs` collector before grading.

## Considered Options

- **Edge pre-computes, pure grader reads** (chosen). Exactly the `final_state`
  precedent (ADR 0001): the runner computes the value at the edge; the pure grader
  reads it and never performs I/O. `JudgeVerdict` is the *only* channel from edge
  to pure core, so it is self-describing (carries `judge_model` + `prompt_hash`),
  letting the pure grader populate `GradeResult.evidence` with no I/O dependency.
  Keeps dispatch single-pass and `AllOf` aggregation untouched.
- **A `needs_judge` marker `GradeResult` re-graded in a second pass.** Rejected:
  forces two-pass grading and a mutable "fill in the verdict" step that breaks
  `AllOf`'s single-pass, no-short-circuit aggregation (ADR 0003).
- **Inject an http client into `grade_trajectory`.** Rejected: collapses the
  functional core into the shell and contaminates *every* deterministic grader
  with an I/O dependency it does not need.

## Consequences

`grade_trajectory` and `grade_all_of` gain one additive optional parameter
(`verdicts`, default empty `Mapping`); all existing call sites and the dispatch
tests pass unchanged. The judge's *only* I/O is the one edge (`run_judge`), which
reuses the existing `runners/client.chat_completion`. A failed judge call is a
serializable `JudgeError` at its key (mirroring `ToolFailure`/`ParseFailure`),
producing a structured non-pass in the pure grader-never a silent pass, never an
uncaught exception in the verdict map. This ADR generalizes: it is the rule for
any future edge-backed grader (e.g. `ExecutionSpec`, Weeks 5-6) — pre-compute the
effectful input, thread it as immutable data, keep the grader pure.
