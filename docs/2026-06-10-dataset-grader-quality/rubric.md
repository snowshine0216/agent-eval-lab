# Workspace-world v2 — task validity rubric

**Version: `rubric-v1`** — every shipped v2 task carries `metadata.review = "passed:rubric-v1"`.

This is the **author's task-validity** checklist — a distinct artifact from any
judge rubric (item 003). Every task in `workspace_tool_use_v2.jsonl` must pass all
seven checks; the per-task verdict is recorded in `metadata.review` (source of truth,
append-only with the row) and mirrored in `review-ledger.md` (regenerable audit view).

## Checklist (every task must pass a–g)

- **(a) Unambiguous** — exactly one defensible correct outcome. For derived tasks the
  min/max/filter has a unique answer (no two candidates share the extremal value).
- **(b) Single-capability** — isolates exactly one capability; if two are needed,
  label the dominant one and note the secondary in the ledger.
- **(c) Verification matches intent** — path-sensitive (`tool_call_match`) only where
  the *action chosen* is what we grade; path-independent (`final_state`) for outcome;
  policy clauses encoded as `TrajectorySpec`, never left as prose.
- **(d) Schema-valid, registered-only** — every `ExpectedToolCall` / final-state path
  schema-validates against the v2 tools and references only registered tools; no
  distractor is ever the expected path.
- **(e) Minimal-but-sufficient `initial_state`** — exactly the accounts/tickets/docs/
  emails the task needs plus the decoys that make the hard tier hard, nothing
  decorative; all four roots present (even when `{}`).
- **(f) Deterministic & auto-scorable** — no clock/RNG dependence; dates are literal
  ISO strings.
- **(g) The knob is the hardness** — the stated `difficulty_knob` is actually the thing
  that makes the task hard (the human gate the pure state-dependency proxy cannot prove).

## Mechanical backstop

`tests/datasets/test_workspace_tool_use_v2.py` enforces (a)-partial, (c), (d), (e), (f),
and the structural witness of (g) (the anti-rote-chain proxy) over all 50 tasks. Checks
(a)-full, (b), and (g)-semantic are human gates recorded in the ledger.

## Re-review

Re-reviewing under a new rubric is a **new dataset version** (a new `version` string +
`world_template_id`), not an in-place row edit — `metadata.review` is frozen with the
append-only row. A ledger edit can never un-gate a row.
