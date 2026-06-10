Verdict: PASS

Subagent: opus
Questions resolved: 8 (Q1–Q8; Q5/Q8 confirmed no-change, Q1/Q3 strengthened the
conformance tooling, Q2/Q4/Q6/Q7 produced spec corrections + one ADR)

## Docs touched (blob SHAs)

| File | Blob SHA | Change |
|------|----------|--------|
| `CONTEXT.md` | `43d2ef4` | +9 dataset-engineering terms; +1 dialogue turn exercising them |
| `docs/adr/0004-per-task-max-steps-is-data-runner-wiring-deferred.md` | `f7398ec` | new ADR (Q2) |
| `docs/2026-06-10-dataset-grader-quality/items/002-spec.md` | `bc6fd13` | refined in place (below) |
| `docs/2026-06-10-dataset-grader-quality/items/002-grill.md` | self | this file |

## Spec refined (blob SHA `bc6fd13`)

Inline strike-through corrections (nothing deleted) + `## Resolved decisions` appended:
- **AC 4** — struck `provenance:"hand_authored"` → `"hand_written"` (Q7); added the
  `ws2-001…ws2-050` task-id scheme (Q6).
- **AC 7** — added the pure anti–rote-chain *state-dependency proxy* (Q1).
- **AC 8** — rewrote the `max_steps` paragraph: verify gate scoped to
  parse+schema+conformance; runner wiring is a *blocking contract* for item 004 (Q2).
- **AC 10** — hardened: `metadata.review` field is the source of truth; ledger is a
  regenerable view (Q4, against §9 append-only).
- **AC 12** — added check (g) distractor-never-expected (Q3) and (h) state-dependency
  proxy (Q1).

## Resolved decisions (Q / A / Rationale / Doc impact)

**Q1 — Does the hard tier actually discriminate, or can a task be long-yet-easy?**
- A: AC 7 + AC 12(h) enforce a pure anti–rote-chain proxy — `multi_step_depth` /
  `derived_argument` tasks must reference ≥1 entity id absent from both `initial_state`
  and the prompt (a minted next-id or a `list_tickets`/`find_account`-surfaced id);
  rubric item (g) is the human gate.
- Rationale: a pure test cannot prove the sufficient semantic property (needs a live
  model — item 004) but can enforce a necessary structural witness every rote chain
  fails, reusing AC 12e's deterministic next-id machinery. Converts "designed to
  discriminate" from assertion to auditable property.
- Doc impact: spec AC 7, AC 12(h); CONTEXT.md State-dependent chain / Difficulty knob /
  Tier.

**Q2 — Does deferring runner wiring leave T3/T4 unrunnable for 002's verify gate?**
- A: Defer wiring to item 004; scope 002's verify gate to parse + schema + conformance
  (pure, no live model). Ship the `metadata.max_steps` field + data + a conformance
  floor (`max_steps >= dependent_calls + 2`). Wiring per-task `max_steps` through
  `multi_run.py`/`cli.py` is a *blocking contract* for 004.
- Rationale: runner budget is a global `max_steps` defaulting to 6 (`cli.py`;
  `loop.py` `for _ in range(max_steps)`); a dependent 8-call chain needs 9–10. AC 13
  forbids a live run in 002, so wiring now ships untestable code (anti-TDD). The
  silent-failure danger (T3/T4 → `max_steps` stop masquerading as agent failure) is
  mitigated by the conformance floor + the blocking note.
- Doc impact: ADR 0004; spec AC 8; CONTEXT.md max_steps (task hint).

**Q3 — Can an author slip bless a distractor path?**
- A: AC 12(g) asserts distractor-never-expected — no distractor in any
  `ExpectedToolCall` (incl. nested in `AllOf`); no `StateEquals`/`StateContains`
  asserting a distractor signature (`status:"archived"`, `emails.*.state:"draft"`) as
  a passing outcome.
- Rationale: the distractor signature set is closed/enumerable ⇒ pure, total check;
  makes `distractor_resistance` a capability a typo cannot invert. No ADR (no real
  alternative).
- Doc impact: spec AC 12(g); CONTEXT.md Distractor tool.

**Q4 — Review evidence: field, ledger, or both, against §9 append-only?**
- A: Both; the `metadata.review` field (riding the append-only row) is the source of
  truth, the `review-ledger.md` is a regenerable human-audit view, never the gate.
- Rationale: §9 append-only governs rows; the field is part of the row (frozen with
  it); re-review = new version, not in-place edit. The ledger is a doc obligated only
  to id-parity. A ledger edit cannot un-gate a row.
- Doc impact: spec AC 10; CONTEXT.md review (task).

**Q5 — Does `world_template_id` need adding for the Weeks 9-10 splits?**
- A: No — already on `TaskMetadata`, v1 populates it (`workspace-v1`), v2 sets
  `workspace-v2`. Zero retrofit; §7 confirms it is the isolation boundary.
- Rationale: carrying it now is free and prevents a retrofit when splits land.
- Doc impact: CONTEXT.md world_template_id; no spec change.

**Q6 — Task-id scheme / file name / version semantics?**
- A: ids `ws2-001…ws2-050` (distinct prefix from v1's `ws-NNN`); file unchanged;
  `metadata.version` is the dataset/world generation string co-varying with
  `world_template_id`, not a per-row revision.
- Rationale: reusing `ws-NNN` collides v1/v2 ids when runs/traces coexist (task id is
  the join key); distinct prefix is the cheap sortable fix.
- Doc impact: spec AC 4; CONTEXT.md version (dataset).

**Q7 — `provenance`: `"hand_authored"` vs v1's `"hand_written"`?**
- A: v2 uses `"hand_written"` (match v1); `"hand_authored"` struck.
- Rationale: provenance is counted in the dataset card (§9); a synonym fractures the
  aggregate. One concept, one canonical term.
- Doc impact: spec AC 4; CONTEXT.md provenance (synonyms under _Avoid_).

**Q8 — New `VerificationSpec` / constraint variants?**
- A: No (confirmed against item 001's union + grader code). Parser-gap escape hatch
  stands.
- Doc impact: none.
