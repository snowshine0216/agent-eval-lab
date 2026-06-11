# Execution verdicts ride the existing verdict map, keyed by a pure execution hash

ADR-0005 named `ExecutionSpec` as the next edge-backed grader. Its verdicts thread
through the **same** `verdicts` mapping `grade_trajectory`/`grade_all_of` already
accept — values discriminated by `isinstance`, so `JudgeVerdict`s and
`ExecutionVerdict`s coexist in one map — keyed by `execution_hash(spec, final_tree)`:
sha256 over the canonical-JSON rendering (the `prompt_hash` convention) of
`held_out_tests`, the final tree, and the **raw** `timeout_s` field (`null` when
`None`). The oracle edge (`runners/oracle_edge.py`) precomputes post-trajectory —
the final tree is only knowable then — and an exception never escapes into the map:
failures are serializable `ExecutionError`s at the same key.

## Considered Options

- **Shared hash-keyed map** (chosen). Zero signature churn through
  dispatch/composite; the hash is a pure function of every interpretation-affecting
  input, computable on both sides of the boundary, and well-defined even when the
  overlay would collide (it hashes spec and tree separately, never the combined
  tree). `isinstance` discrimination is already the judge pattern.
- **A separate `executions` parameter.** Rejected: signature churn through every
  grading call site for no semantic gain.
- **In-grader execution.** Rejected: collapses the functional core — ADR-0005's
  rejected option restated.

## Consequences

This fixes the reading of ADR-0008's closing sentence: "reads the recorded results"
means the edge-precomputed `ExecutionVerdict` threaded in as data — **not** the
agent's mid-run `run_tests` records, which cover only the visible tests and would be
a gameable oracle. Hashing the raw `timeout_s` (not the edge-resolved default) keeps
the hash computable without edge policy; specs differing only in `None` vs an
explicit default hash apart and each get their own verdict — cross-spec dedup is a
non-goal. A negligible-probability hash collision with a judge `prompt_hash` is
harmless: each grader type-checks the value at its key and emits a structured
non-pass on a foreign type.
