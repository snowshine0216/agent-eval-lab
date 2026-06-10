Verdict: FAIL

Subagent: sonnet / Plan checklist items: 13 (A1–A7, B1, C, D, E, F, G1, G2, H) / Verified present in diff: 13 / Drift findings: 4 (details below)

---

## Plan checklist status

All 13 plan tasks are present in the diff:

- A1–A7 (tools + determinism): squashed into one commit `bfe66dc` — content is byte-for-byte identical to plan specs; all tool schemas, impls, `_IMPLS` wiring, `_next_email_id`, and the determinism property test are present. Process deviation only.
- B1 (TaskMetadata fields): `max_steps` and `review` added to schema.py and parse.py; tests added to test_parse.py. Matches plan exactly.
- C (conformance suite): present at `tests/datasets/test_workspace_tool_use_v2.py`. Two deviations — see DRIFT-1 and DRIFT-2 below.
- D/E (50 tasks): `examples/datasets/workspace_tool_use_v2.jsonl` has exactly 50 lines; ids ws2-001..ws2-050; all six capabilities present; tier mix 5/12/22/11 verified.
- F (taxonomy.md): byte-for-byte identical to plan text.
- G1 (rubric.md): byte-for-byte identical to plan text.
- G2 (review-ledger.md): 50 rows, all ids present, ledger parity test passes.
- H (full gate): 223 tests pass, ruff clean, v1 files untouched (0-byte diff).

---

## Drift findings

### DRIFT-1 — Histogram whitelist gained `"trajectory"` (plan omission, AMEND)

**Evidence:** `tests/datasets/test_workspace_tool_use_v2.py:188`
```python
assert types <= {"tool_call_match", "final_state", "all_of", "trajectory"}
```
Plan (`002-plan.md:1343`) specifies:
```python
assert types <= {"tool_call_match", "final_state", "all_of"}
```

**Analysis:** `TrajectorySpec.type == "trajectory"` (schema.py line 78). The `_spec_type_names` function recurses into `AllOf` and reaches the inner `TrajectorySpec`, whose `.type` field is `"trajectory"`. Without `"trajectory"` in the whitelist, the test would fail on every `all_of` task (ws2-040..ws2-050). The plan omitted this value from an enumerable closed set — the impl's fix is correct and necessary.

**Action:** AMEND plan — one-line rationale added inline. Rationale: `TrajectorySpec.type=="trajectory"` is surfaced by `_spec_type_names` when recursing into AllOf; the plan omitted it from the whitelist.

---

### DRIFT-2 — Precondition test gained `_minted_email_ids` helper (plan omission, AMEND)

**Evidence:** `tests/datasets/test_workspace_tool_use_v2.py:91–101` (the `_minted_email_ids` function) and line 162:
```python
mintable |= _minted_email_ids(task.initial_state, 4)
```
Plan (`002-plan.md:1373–1382`) provides `_minted_ticket_ids` but not `_minted_email_ids`.

**Analysis:** 13 tasks (ws2-022, 023, 024, 027, 031, 032, 034, 036, 040, 042, 043, 045, 046) reference `emails.e-1.*` in their final-state verification but start with `initial_state.emails == {}`. Without `_minted_email_ids`, the precondition check would flag all 13 as dangling references. The plan explicitly defines `_next_email_id` and requires `send_email` tasks, so the omission of the corresponding mintable helper is a plan gap, not a scope expansion.

**Action:** AMEND plan — one-line rationale added inline. Rationale: tasks whose `send_email` creates `e-<n>` need `_minted_email_ids` parallel to `_minted_ticket_ids`; the plan omitted it despite specifying `_next_email_id`.

---

### DRIFT-3 — KNOB REASSIGNMENT on 10 tasks: FAIL (divergent from explicit plan specification)

**Evidence — plan allocation table (`002-plan.md:998–1048`) specifies:**
| task | plan knob | impl knob |
|------|-----------|-----------|
| ws2-020 | `multi_step_depth` | `distractor_count` |
| ws2-026 | `multi_step_depth` | `distractor_count` |
| ws2-028 | `derived_argument` | `argument_complexity` |
| ws2-029 | `derived_argument` | `argument_complexity` |
| ws2-030 | `derived_argument` | `argument_complexity` |
| ws2-033 | `derived_argument` | `argument_complexity` |
| ws2-035 | `derived_argument` | `argument_complexity` |
| ws2-037 | `derived_argument` | `argument_complexity` |
| ws2-038 | `derived_argument` | `argument_complexity` |
| ws2-039 | `derived_argument` | `argument_complexity` |

**The plan exemplars (`002-plan.md:1072–1090`) are the most authoritative statement** — they give complete JSONL with `"difficulty_knob": "derived_argument"` for ws2-028 (the T4 exemplar) and ws2-029 (the T3 exemplar). The impl directly contradicts both exemplars.

**Are the 10 tasks still genuinely hard?** Yes — the tasks themselves are semantically correct. All 10 require the model to call `list_tickets` (or `find_account`), read the returned data, and compute a derived argument (min/max by date, priority ranking, count gate). That IS `derived_argument` by the taxonomy's own definition. The hardness is not watered down, but the label `argument_complexity` is definitionally wrong: the taxonomy doc (committed in this branch) defines `argument_complexity` as "extract literal/nested/enum/date args from NL" — a T2 mechanism — not "reason over a tool result."

**Impact on anti-rote-chain proxy coverage:** The conformance proxy (`test_state_dependency_proxy_for_derived_tasks`) fires only for tasks with `difficulty_knob in {multi_step_depth, derived_argument}`. After reassignment, 12 of 33 T3+T4 tasks are checked (ws2-018, 019, 021, 022, 023, 024, 025, 027, 031, 032, 034, 036). Before reassignment, 22 of 33 would have been checked. The 8 tasks moved to `argument_complexity` skip the proxy entirely — the conformance test no longer enforces the AC7 structural witness on ws2-028–030, 033, 035, 037–039.

**Does AC7 still hold?** AC7 requires "at least 15 tasks require a dependent chain of ≥4 tool calls where at least one call's arguments are unknowable without a prior call's result." The 10 reassigned tasks are semantically state-dependent (the correct T-id to close cannot be determined without calling `list_tickets`), but their knob no longer signals this to the proxy. The proxy's coverage has dropped from the intended ≥22 to 12 — meaning the anti-rote guarantee is structurally weakened even though the task content is correct.

**Resolution rule:** Significant divergence + specific plan text (the exemplars are the most explicit specification) → **Verdict: FAIL**.

**Tasks requiring re-authoring (knob correction only, content is correct):**
- ws2-028, ws2-029, ws2-030, ws2-033, ws2-035, ws2-037, ws2-038, ws2-039 → change `difficulty_knob` from `argument_complexity` to `derived_argument`
- ws2-020, ws2-026 → change `difficulty_knob` from `distractor_count` to `multi_step_depth`

---

### DRIFT-4 — A1–A7 squashed into one commit (process deviation, INCIDENTAL)

**Evidence:** Commit `bfe66dc` contains all tool changes instead of 7 separate commits per plan A1–A7 step 7 instructions.

**Analysis:** Content is correct; all tool schemas, impls, tests, and wiring are present and match plan specifications. The squash is a process deviation with zero content impact. The plan's commit messages were a TDD tracking aid, not a content gate.

**Action:** Incidental — no amendment needed.

---

## State-dependent reasoning count

**By knob (conformance proxy, strict):** 12 of 33 T3+T4 tasks carry `difficulty_knob` in `{multi_step_depth, derived_argument}`:
ws2-018, ws2-019, ws2-021, ws2-022, ws2-023, ws2-024, ws2-025, ws2-027, ws2-031, ws2-032, ws2-034, ws2-036.

**By semantics (model must use prior call's result):** 24 of 33 T3+T4 tasks genuinely require using a prior call's result to determine which entity to act on. This includes the 12 above plus the 10 reassigned tasks (ws2-020, 026, 028–030, 033, 035, 037–039) and ws2-044, ws2-049.

**The gap:** 10 tasks are semantically state-dependent but not structurally proxied because their knob was changed to `argument_complexity` or `distractor_count`. The correct knob for ws2-028–030, 033, 035, 037–039 is `derived_argument`; for ws2-020 and ws2-026 it is `multi_step_depth`. Correcting these 10 knobs would bring the proxy coverage to 22/33, matching the plan's intent.

---

## Summary

| finding | type | action |
|---------|------|--------|
| DRIFT-1: histogram whitelist missing `"trajectory"` | plan omission | AMEND plan |
| DRIFT-2: precondition check missing `_minted_email_ids` | plan omission | AMEND plan |
| DRIFT-3: knob reassignment on 10 tasks contradicts plan exemplars | significant divergence | FAIL — re-author knob fields |
| DRIFT-4: A1–A7 squash | process deviation | incidental |

**Primary failure:** DRIFT-3. The 10 tasks need `difficulty_knob` corrections only (content, scenarios, and initial_state are all correct). The fix is a one-line metadata change per task in the JSONL plus ledger updates.
