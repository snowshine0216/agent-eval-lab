# B-set spike grade is an owner verdict joined at report time

The B-1 live spike (docs/superpowers/specs/2026-06-17-b-set-live-spike-design.md) grades by
**human review** — an **owner verdict** against the **definition-match checklist** — instead
of an automated readback oracle (deferred to the production B runner). But `RunResult.grade:
GradeResult` is **mandatory** (records/grade.py): a run record cannot exist without a grade.
At run time (Phase 1) the grade does not yet exist — it is produced in Phase 2 when the owner
opens the saved MSTR object and scores it. So the live-run artifact **cannot** be a
`RunResult`.

**Decision:** `run-b` persists a **grade-less `BTrial`** (`records/b_trial.py`: `run_uid`,
`condition_id`, `task_id`/arm, `save_name`, `folder`, `Trajectory`, `invalid`,
`invalid_reason` — no `GradeResult`) to `trials-b-<slug>-<task_id>.jsonl`. `report-b` joins
each `BTrial` with its **owner verdict** (a separate verdicts file) to construct the
`GradeResult` + `RunResult` **purely at report time**, then reuses the existing
`pass_at_1` / efficiency metric layer. No `GradeResult` is fabricated at run time. This keeps
"the verdict, not the runner, is the grade source" honest (CONTEXT.md: *owner verdict*).

## Considered Options

- **Grade-less `BTrial`; `report-b` builds the grade from the owner verdict** (chosen). The
  on-disk unit carries everything except the grade; the grade is constructed once, at report
  time, from `(BTrial, owner verdict)`. Env/provider **invalid**-tagging needs no grade — it
  reads the `Trajectory` parse_failure + `env_health` — so the **validity mask** still works
  pre-grade (D34 replacement on the env axis).
- **Write a `RunResult` with a placeholder/pending `GradeResult` (`passed=False`) at run time,
  overridden by `report-b`.** Rejected: a `passed=False` on disk is a landmine — any consumer
  reading the artifact before the owner grades (`report-m1`, the fc-v4 classifier, a stray
  rollup) counts it as a model FAIL. That is exactly the silent miscount the project's
  anti-silent discipline forbids (cf. the node-v16 incident, ADR-0018).
- **Make `RunResult.grade` Optional project-wide.** Rejected: it ripples through every grade
  consumer (metrics, classifier, every report) to accommodate one human-scored spike.
  `RunResult` is the canonical *graded* record and stays non-optional; the spike adapts to it,
  not the reverse.

## Consequences

The B spike's on-disk unit is `BTrial`, not `RunResult`, and `report-b` is the **only** place a
B grade is constructed — purely, from `(BTrial, owner verdict)`. This is spike-scoped: when the
production B runner later automates the evaluator readback oracle, it produces a real
`GradeResult` at run time and writes `RunResult` like the other domains, so the `BTrial` path
does not constrain it. The `trials-b-*.jsonl` name (not `runs-b-*`) signals the artifact is a
trial record, not a graded run — a reader who expects a `GradeResult` and finds none is meant
to look here.
