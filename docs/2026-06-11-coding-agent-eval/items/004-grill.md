Verdict: PASS

Subagent: fable
Questions resolved: 15
Docs touched (commit db76cdc):
  - CONTEXT.md (terms added: RunClassification (failure classification),
    world binding, task-defect candidate; term updated: FailureCategory —
    cross-ref distinguishing the grade-level taxonomy from the derived
    task/agent/harness axis)
  - docs/adr/0013-failure-classification-is-derived-total-and-versioned.md (new)
Spec refined: items/004-spec.md (commit db76cdc)

## Resolved decisions

- Q: Is the fc-v1 mapping table exhaustive over the evidence shapes item 002's
  grader actually produces — does every reachable combination classify
  deterministically, no fallthrough?
  A: It had one leak: the "kind `unknown` → foreign_verdict" row. Verified in
  code that `graders/execution._error_evidence` records
  `getattr(value, "kind", "unknown")` — an OPEN string — so a foreign value at
  a colliding hash (e.g. a `JudgeError` with kind `transport`/`parse`) matched
  no error row and fell through to `agent_failure/other_miss`. Fixed: the
  error branch closes with an any-other-kind fallback →
  `harness_failure/foreign_verdict`; rows 7/8 reordered.
  Rationale: a verdict-plumbing fault must never be filed as an agent miss;
  the branch is now exhaustive by construction, not by enumeration.
  Doc impact: criterion 7 table + strike-through; ADR-0013; Hypothesis test
  gains a foreign-kind case.

- Q: Is `tree_collision → agent` sound given ADR-0012?
  A: Yes, on three mechanical facts verified in code: conformance bans oracle
  paths equal/prefix-colliding with any initial-tree path (ADR-0012);
  code-world has no delete tool, so the final tree is initial ∪ agent writes;
  exact-path equality is displacement, never collision (`prefix_collision`
  returns false on equality, ADR-0010). A collision pair therefore always
  involves an agent-minted spelling. ADR-0012's consequences pre-authorize the
  row.
  Rationale: the judgment is conditional on the conformance contract — stated
  in the footnote so a reviewer can re-litigate with the cited evidence.
  Doc impact: criterion 7 footnote sharpened; ADR-0013 judgment row.

- Q: Is the parse_failure harness/agent split mechanically pinned, or a magic
  string duplicated from `runners/loop.py`?
  A: It was a magic string. Fixed: the literal "no choices in provider
  response" is hoisted to a shared constant in `records/trajectory.py`
  (schema-adjacent, pure, no record-shape change), referenced by loop and
  classifier, pinned by a stub-loop integration test.
  Rationale: string drift would silently re-route harness failures into
  `malformed_reply`. Also recorded: message-level emptiness ("neither content
  nor tool_calls") stays agent-side — the envelope was well-formed.
  Doc impact: criterion 7 + Open-question 5 extended; ADR-0013.

- Q: Does the world-resolver-from-available_tools approach conflict with any
  schema ADR, and what does an empty tool list resolve to?
  A: No conflict — resolution reads only the frozen `available_tools` field;
  no metadata, no flag, no schema change. Empty list raises `ValueError`
  (verified: zero tool-less tasks across v1/v2/code_repair_v1). Registry
  name-space disjointness (workspace 9 ∩ code 4 = ∅, verified in code) becomes
  a tested invariant.
  Rationale: fail loud beats inventing semantics for a case with no data; the
  closed two-entry table is only sound while names stay disjoint.
  Doc impact: criterion 1 sharpened; CONTEXT.md term world binding.

- Q: What is excluded from the report's byte-determinism claim (timestamps,
  latencies), mirroring Weeks 3-4?
  A: Nothing. No generation timestamp exists to exempt (the Weeks 3-4
  validation renderer emits none — verified); latency and cost render only
  from recorded usage data and the committed prices file.
  Rationale: an exemption list is a leak waiting to widen; pure
  build+render over committed inputs needs no exceptions.
  Doc impact: criteria 16 and 19 sharpened.

- Q: Does committing run JSONLs under docs/<run-dir>/runs/ conflict with any
  repo convention?
  A: No — `git check-ignore` verified `/reports/` and `/runs/` are
  root-anchored patterns; the run-dir subdirectory is committable unchanged.
  New obligation: the JSONLs embed agent solution trees and oracle stdout, so
  they join the Weeks 9-10 never-train manifest (003 sidecar precedent).
  Rationale: the exit gate's regeneration claim must be reviewer-verifiable
  from the repo alone; the never-train note keeps the eval→data→finetune
  boundary intact.
  Doc impact: criterion 13 extended.

- Q: Why is an agent hang named `sandbox_timeout`?
  A: Renamed `oracle_timeout`. The timeout fires in the oracle run over the
  submitted tree; conformance proves the reference solution finishes inside
  the same budget, so the hang indicts the agent's code. `sandbox_*` is
  harness vocabulary (`sandbox_fault`). Count stays 15.
  Rationale: subcategory names must not imply the wrong category axis.
  Doc impact: criterion 7 table + strike-through; Open-question 17 note.

- Q: Can a run with a recorded parse_failure still classify as passed?
  A: Yes — rows 2-16 now explicitly require `grade.passed == False`; row 1
  wins first (e.g. a FinalStateSpec already satisfied before the failed turn).
  Rationale: priority-first-match must be stated, not assumed.
  Doc impact: criterion 7 preamble.

- Q: Does the exec_ev walk survive the JSONL round-trip?
  A: Yes — `sub_results` entries deserialize as plain dicts (verified in
  composite.py + serialize.py + `_load_run_results`); the walk is specified
  over dict keys, first execution leg in declared order, recursing nested
  all_of entries.
  Rationale: the classifier consumes loaded artifacts, never live dataclasses.
  Doc impact: criterion 7 preamble.

- Q: How does the task-defect unanimity rule treat a condition with no records
  for a task?
  A: It contributes nothing (vacuous) — unanimity quantifies over non-blocked
  conditions with ≥1 record of the task; the queue renders per-task
  n_conditions/n_runs so evidence strength is visible.
  Rationale: no fabricated evidence, no invented minimum-condition threshold.
  Doc impact: criterion 9 sharpened + new test case.

- Q: report-validation's parser discards the `condition_id` segment of
  `--runs` — does report-final need it?
  A: Yes, live: condition_id is derived from records (heterogeneous file =
  loud error), cross-checked against the segment when present, and is the
  prices.json join key. prices.json shape pinned:
  {"snapshot_date", "prices": {condition_id: {input_per_mtok,
  output_per_mtok}}}.
  Rationale: the cost section must regenerate from data, not from a CLI label.
  Doc impact: criteria 14 and 15 sharpened.

- Q: Sharing the discriminativeness rule with reports/validation.py risks
  byte-drift on a frozen surface — guarded how?
  A: Any extraction keeps report-validation output byte-identical over a
  fixture run set, proven by a regression test.
  Rationale: the committed Weeks 3-4 reports are regenerable artifacts; a
  drifting render orphans them.
  Doc impact: criterion 17 extended.

- Q: Is `step_exhaustion` always an agent failure, given the validation
  report calls such runs "starvation suspects"?
  A: Kept agent: the budget is data-validated (per-task metadata.max_steps
  honored via effective_max_steps — ADR-0004 wiring verified landed in
  multi_run.py — and conformance-floored), so exhaustion is the agent's
  spend; the starvation lens stays available in working artifacts.
  Rationale: a validated budget shifts the burden onto the run.
  Doc impact: criterion 7 footnote sharpened.

- Q: Which decisions are ADR-worthy (three-of-three)?
  A: One: ADR-0013 — fc-v1 classification is derived/total/versioned, with the
  judgment rows. World resolver and committed-runs divergence are spec-level
  resolved decisions (reversible — two-of-three).
  Rationale: fc-v1 semantics anchor Weeks 9-10 mining and Release #1;
  tree_collision→agent and no-unknown-bucket will surprise future readers;
  derived-vs-stored was a real trade-off.
  Doc impact: ADR-0013 created.

- Q: Does criterion 6's Hypothesis property test add a new dependency or CI
  lane?
  A: No — hypothesis>=6.100 is already in pyproject.toml (verified).
  Rationale: criterion 22's no-new-lane constraint holds as written.
  Doc impact: none.
