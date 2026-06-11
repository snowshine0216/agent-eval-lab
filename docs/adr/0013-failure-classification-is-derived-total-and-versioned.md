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
