# Failure classification is a derived, total, versioned mapping (fc-v1), never stored

Item 004 needs the roadmap's explicit task/agent/harness failure classification,
and Weeks 9-10 failure mining plus Release #1 consume its categories as stable
input. We classify with a pure, total, priority-ordered, first-match-wins table
(`reports/classify.py`, version `fc-v1`) computed at **report time** over the
frozen `RunResult` — reading only the mechanical discriminators earlier items
left on the record (suite status, execution-error kind, parse failure,
stop reason, `failure_reason`) — and never store the classification on any
record or artifact.

## Considered Options

- **Derived, total, versioned table** (chosen). The frozen `RunResult` schema
  and the closed `FailureCategory` literal are untouched; already-captured run
  artifacts classify retroactively; a classifier-version bump (`fc-v2`) is a
  pure re-render of committed runs, never a model re-run. Totality (a Hypothesis
  property: never raises, always a closed category) plus first-match priority
  makes every reachable evidence combination classify deterministically — no
  fallthrough.
- **Store the classification on `RunResult`.** Rejected: touches a frozen
  schema, orphans every already-captured artifact, and freezes classifier
  semantics into data — a semantics bug would require re-running models.
- **An open subcategory string or an `unknown` category.** Rejected: free-form
  strings fracture the counts Weeks 9-10 mines against (the provenance lesson),
  and an unknown bucket invites lazy triage; the fallback rows make the
  function total without one.
- **Auto-classifying unanimous failures as `task_failure`.** Rejected: the
  conformance suite already proves solvability/breadth/symptom mechanically, so
  "all models failed ⇒ task defect" would misclassify genuinely hard tasks —
  exactly the discriminativeness corruption Weeks 3-4 documented. Unanimous
  failures are *flagged for human review* instead; the only mechanical
  post-conformance task-defect signal is an empty oracle (`no_tests`).

## Documented judgment rows

- `tree_collision` → **agent**: oracle paths are disjoint from every
  initial-tree path (ADR-0012's conformance contract) and code-world has no
  delete tool, so a canonical-prefix collision can only be minted by the run's
  own write (exact-path equality is displacement, not collision, per ADR-0010).
  Conditional on the conformance contract — fc-v1 is declared for
  conformance-proven code-repair datasets.
- `parse_failure` splits **harness/agent** on the loop's empty-choices literal
  (provider delivered no completion → harness) vs every other parse error (the
  model emitted an unparseable payload → agent); the literal is a shared
  constant, pinned by a stub-loop test, so the split cannot drift.
- Unrecognized execution-error kinds → **harness** (`foreign_verdict`): the
  evidence `kind` is an open string (a foreign value at a colliding hash
  carries its own `kind` attribute), so the error branch closes with an
  any-other-kind fallback rather than leaking foreign kinds into agent rows.
- Budget exhaustion (`stop_reason == "max_steps"`) outranks oracle statuses: a
  truncated attempt's red oracle is an artifact of the truncation.

## Consequences

The fc-v1 table is frozen with its version: changing any row's semantics mints
`fc-v2` and re-renders; committed reports name the classifier version so their
numbers stay attributable. Downstream (Weeks 9-10 mining, Release #1) joins on
`(classifier_version, category, subcategory)`. The task/agent/harness axis
lives only in `RunClassification` — `FailureCategory` gains no values, and the
report layer is the only consumer surface this slice.

## fc-v2 amendment (2026-06-11)

A harness defect discovered during item 004 validity review triggered the first
classifier version bump. fc-v2 (`reports/classify.py`, `CLASSIFIER_VERSION =
"fc-v2"`) changes exactly two things relative to fc-v1:

- **New subcategory `token_budget_exhausted`** (category: `agent_failure`):
  parse_failure runs where `usage.completion_tokens >= trajectory.max_tokens`
  indicate the reasoning channel was cut off by the declared budget, not a
  malformed model reply. This requires the explicit `--max-tokens` flag (default
  4096) added to `run-baseline` and recorded per trajectory; artifacts without
  `trajectory.max_tokens` (pre-fc-v2 runs) fall through to `malformed_reply`
  unchanged, preserving backward compatibility.
- **None-guard for `stop_reason == "parse_failure"` with `parse_failure is
  None`**: fc-v1 raised `AttributeError` on this path (a harness wiring defect);
  fc-v2 classifies it as `harness_failure/sandbox_fault` so the function is
  total as advertised.

All committed run artifacts from the coding-agent-eval slice were re-rendered
under fc-v2; the Weeks 3-4 workspace-world reports are unaffected (no
`max_tokens` field, no execution grading, no path that reaches the None-guard).

## fc-v4 amendment (2026-06-15)

The harness-rounds/F-ablation phase (design 2026-06-15) requires two declared-
but-unenforced contracts to be honoured in the reporting layer, mandating a
classifier version bump (item 001). fc-v4 (`reports/classify.py`,
`CLASSIFIER_VERSION = "fc-v4"`) changes exactly three rows relative to fc-v3 and
adds one closed-vocabulary value:

- **`node_execution` leaf fix (Row E.1):** `first_execution_evidence` now
  matches the `"node_execution"` grader_id, not only `"execution"`. The F-set
  node oracle (`graders/node_execution.py`) emits the identical evidence shape
  (`execution`/`status`/`counts`), so a failing node-F run now classifies as
  `agent_failure / oracle_red` instead of the catch-all `other_miss`. Verified
  against a real failing node-F record's evidence shape.
- **New subcategory `budget_exhausted` (agent_failure) (Rows E.2/E.3):** a run
  that hit a budget cap — `stop_reason in {safety_cap, max_rounds}` or the
  `safety_cap_bound` / `max_rounds_bound` flags — classifies as
  `agent_failure / budget_exhausted`. It guards the row-1 `passed`
  short-circuit (a graded-pass that was capped is NOT a reliable pass,
  consistent with the §D.1 `pass^k` censor) and outranks the oracle-status rows.
  `max_rounds_bound` is read defensively (default `False`); it arrives on the
  trajectory record in item 002, so item 001 lands standalone and every existing
  record (which lacks the field) is unaffected. The closed `Subcategory`
  vocabulary grows 19 → 20.
- **Legacy `max_steps` is unchanged:** it keeps its `step_exhaustion` bucket. A
  `max_steps` stop is a *turn truncation* (the loop hard-stopped mid-turn),
  semantically distinct from an end-of-round *budget cap*; the documented fc-v1
  judgment row ("`max_steps` outranks oracle statuses") still holds.

Re-rendering the committed M1 reports under fc-v4 moves taxonomy outputs (failing
node-F runs leave `other_miss`; any cap-bound run enters `budget_exhausted`) but
moves **zero `pass^k` numbers**: of the committed historical records, none both
graded-passed and were budget-capped (proven by
`tests/metrics/test_reliability_historical.py`). The Weeks 3-4 / code-repair
workspace-world reports are unaffected (no `node_execution` grader, no cap-bound
runs). Downstream mining keeps joining on
`(classifier_version, category, subcategory)`.
