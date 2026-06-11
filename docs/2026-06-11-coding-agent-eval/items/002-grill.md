Verdict: PASS

Subagent: fable
Questions resolved: 15
Docs touched:
  - CONTEXT.md (commit aa6e8ed)
  - docs/adr/0008-mid-trajectory-effects-bridge-through-effect-requests.md (commit aa6e8ed)
  - docs/adr/0010-oracle-tests-overlay-final-tree-oracle-wins.md (commit aa6e8ed)
  - docs/adr/0011-execution-verdicts-share-the-verdict-map-keyed-by-execution-hash.md (commit aa6e8ed)
Spec refined: items/002-spec.md (commit aa6e8ed)

## Resolved decisions

- Q: Canonical term for `held_out_tests` — "oracle tests", "hidden tests", or "held-out suite"?
  A: Oracle tests — held-out test files the agent never sees; distinct from the visible tests `run_tests` covers mid-trajectory.
  Rationale: MASTER-SPEC already says "tests are the oracle"; one term, one meaning.
  Doc impact: CONTEXT.md term oracle tests

- Q: The spec names the new module `runners/execution_edge.py`, but CONTEXT.md binds "execution edge" to `runners/pytest_edge.py` — one word, two modules?
  A: Rename to `runners/oracle_edge.py`; the concept is the oracle edge (grading-side precompute boundary atop the execution edge).
  Rationale: one meaning per word is the glossary's prime directive; renaming an unwritten module is free, renaming an established term is not.
  Doc impact: CONTEXT.md terms oracle edge + execution edge cross-reference

- Q: Who wins an overlay collision between the agent's tree and the oracle tests?
  A: Oracle-wins on exact paths with displaced paths recorded as evidence; canonical-prefix collisions are structured `tree_collision` errors, never crashes.
  Rationale: agent-wins is a reward-hack vector; error-on-exact-collision punishes paths the agent cannot know exist.
  Doc impact: ADR-0010; CONTEXT.md terms overlay (oracle-wins), displaced path

- Q: How do execution verdicts reach the pure grader — a new parameter, in-grader execution, or the existing map?
  A: The existing `verdicts` map, values discriminated by isinstance, keyed by `execution_hash`, precomputed post-trajectory at the oracle edge.
  Rationale: ADR-0005's rule with zero signature churn; the judge pattern generalizes cleanly.
  Doc impact: ADR-0011; CONTEXT.md terms execution hash, ExecutionVerdict

- Q: Does ADR-0008's closing sentence ("the ExecutionSpec grader reads the recorded results") mean reusing the agent's mid-run `run_tests` records?
  A: No — it means the edge-precomputed ExecutionVerdict threaded in as data; mid-run results cover only visible tests and would be a gameable oracle.
  Rationale: a real ambiguity that could steer the plan phase into the wrong design.
  Doc impact: ADR-0008 (clarifying sentence appended); ADR-0011

- Q: Does `execution_hash` cover the raw `timeout_s` field or the edge-resolved effective timeout?
  A: The raw field (null when None).
  Rationale: the hash must be computable without edge policy; None-vs-explicit-default dedup is a non-goal.
  Doc impact: ADR-0011

- Q: What exactly is "canonical JSON" for the hash?
  A: The existing `prompt_hash` convention — `json.dumps(..., sort_keys=True)` over deep-plain values.
  Rationale: one canonicalization convention per codebase.
  Doc impact: none

- Q: Criterion 3 demands one shared collision predicate, but the Constraints froze `tools/code_world.py` untouched — contradiction?
  A: Relax by exactly one additive public export of code_world's existing predicate; `pytest_edge`'s duplicate stays as untouched defense-in-depth.
  Rationale: a private cross-module import or a third copy are both worse; "untouched" intended API stability, not zero diffs.
  Doc impact: none (spec constraint struck + corrected)

- Q: Serializer tags for the new verdict records?
  A: "execution_verdict" / "execution_error"; the judge's legacy "verdict" tag stays frozen.
  Rationale: distinct tags keep round-trips total; renaming the legacy tag breaks existing artifacts.
  Doc impact: none

- Q: `timeout_s` parser typing — is `5` (int) valid? `true` (bool)?
  A: Accept int/float, store as float; reject bool explicitly and non-positive values.
  Rationale: JSON has one number type; `_parse_scale` sets the bool-rejection precedent.
  Doc impact: none

- Q: What does `grade_execution` do with a foreign value (e.g. a JudgeVerdict) at its hash key?
  A: The error path with kind "unknown" — mirroring the judge's getattr fallback; never a crash, never a pass.
  Rationale: the grader must be total over arbitrary map contents.
  Doc impact: none

- Q: A self-contained oracle (imports nothing from the repo) would pass over an empty final tree — whose defect?
  A: Item 003's authoring conformance owns "the oracle must exercise the program under repair"; the structural parser stays out.
  Rationale: load-time structural checks cannot know intent; the spec's boundary is right.
  Doc impact: none

- Q: A hand-authored golden `final_state` could carry agent-internal canonical collisions the pure tools would never produce — what happens?
  A: The overlay checks only agent-oracle collisions; an agent-internal collision reaches the materializer's guard and is captured as ExecutionError(kind="harness").
  Rationale: unreachable in production; a fixture defect surfacing as a visible harness record is acceptable.
  Doc impact: none

- Q: Where does `collect_execution_specs` live?
  A: `graders/execution.py`, beside the grader, mirroring `collect_judge_specs` in `graders/judge.py`.
  Rationale: collector and grader share the spec vocabulary; the judge sets the precedent.
  Doc impact: none

- Q: CONTEXT.md's VerificationSpec entry still says "later ExecutionSpec/LlmJudgeSpec" — stale once this item lands?
  A: Update the entry to list all variants, ExecutionSpec included.
  Rationale: the glossary must track the union this item completes.
  Doc impact: CONTEXT.md term VerificationSpec
