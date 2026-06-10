# Validation report — v2 live validation

- Dataset: `workspace_tool_use_v2` · n=50 tasks · k=3 · bootstrap seed=20260610
- Temperature 0.0 was *requested*; no seed is sent and hosted providers are not greedy-deterministic at temp 0, so residual run-to-run variation is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob is the bootstrap RNG.

## Per-condition reliability

| condition | status | tasks | pass@1 | pass^3 [95% CI] |
| --- | --- | --- | --- | --- |
| C1 | complete | 50 | 1.000 | 1.000 [1.000, 1.000] |
| C2 | complete | 50 | 1.000 | 1.000 [1.000, 1.000] |
| C3 | complete | 50 | 0.980 | 0.940 [0.860, 1.000] |
| C4 | complete | 50 | 0.620 | 0.620 [0.480, 0.740] |

## Per-tier pass^3 (accuracy curve)

| condition | T1 | T2 | T3 | T4 |
| --- | --- | --- | --- | --- |
| C1 | 1.000 | 1.000 | 1.000 | 1.000 |
| C2 | 1.000 | 1.000 | 1.000 | 1.000 |
| C3 | 1.000 | 0.917 | 0.909 | 1.000 |
| C4 | 1.000 | 1.000 | 0.318 | 0.636 |

## Failure taxonomy × tier × capability

### C1

| category | tier | capability | count |
| --- | --- | --- | --- |
| (no failures) | — | — | 0 |

### C2

| category | tier | capability | count |
| --- | --- | --- | --- |
| (no failures) | — | — | 0 |

### C3

| category | tier | capability | count |
| --- | --- | --- | --- |
| unclassified | T3 | derived_reasoning | 2 |
| wrong_args | T2 | argument_extraction | 1 |

### C4

| category | tier | capability | count |
| --- | --- | --- | --- |
| unclassified | T3 | derived_reasoning | 27 |
| unclassified | T3 | multi_step_state | 18 |
| unclassified | T4 | constraint_compliance | 6 |
| unclassified | T4 | distractor_resistance | 6 |

## Deterministic vs flaky split

- **C1** — Deterministic failures (all-3-fail): none
  - Flaky (mixed pass/fail across k): none
- **C2** — Deterministic failures (all-3-fail): none
  - Flaky (mixed pass/fail across k): none
- **C3** — Deterministic failures (all-3-fail): none
  - Flaky (mixed pass/fail across k): ws2-015, ws2-031, ws2-032
- **C4** — Deterministic failures (all-3-fail): ws2-018, ws2-020, ws2-023, ws2-024, ws2-025, ws2-028, ws2-029, ws2-030, ws2-032, ws2-034, ws2-035, ws2-036, ws2-037, ws2-038, ws2-039, ws2-040, ws2-042, ws2-044, ws2-049
  - Flaky (mixed pass/fail across k): none

## Budget-floor assertion (AC2 — step-starvation check)

Every task ran with at least its declared `metadata.max_steps` budget (per-task budget honored by `effective_max_steps`; stop_reason='max_steps' only when the loop exhausts the budget, not when the grader emits `step_limit_exceeded`).

| condition | runs hitting max_steps | starvation suspects (failing + exhausted) |
| --- | --- | --- |
| C1 | 0 | none |
| C2 | 0 | none |
| C3 | 0 | none |
| C4 | 0 | none |

## Exemplar trace excerpts (top failure modes)

For each condition, the top failure mode(s) are illustrated with one exemplar (lex-first failing task, run_index=0). Compact: task id, tier/capability, grade evidence, observed tool-call sequence.

### C1

*(no failures — no exemplars)*

### C2

*(no failures — no exemplars)*

### C3

**Failure mode: `unclassified`** — exemplar task `ws2-031` (T3/derived_reasoning)
- Observed tool-call sequence: `get_account(user_id='u-2') → list_tickets(status='open') → draft_email(to='grace@example.com', subject='Your Open Tickets')`

**Failure mode: `wrong_args`** — exemplar task `ws2-015` (T2/argument_extraction)
- Observed tool-call sequence: `send_email(to='ops@example.com', subject='Outage update')`

### C4

**Failure mode: `unclassified`** — exemplar task `ws2-018` (T3/multi_step_state)
- Observed tool-call sequence: `(no tool calls)`


## Per-task pass matrix (task → reliable on each condition)

| task | C1 | C2 | C3 | C4 |
| --- | --- | --- | --- | --- |
| ws2-001 | PASS | PASS | PASS | PASS |
| ws2-002 | PASS | PASS | PASS | PASS |
| ws2-003 | PASS | PASS | PASS | PASS |
| ws2-004 | PASS | PASS | PASS | PASS |
| ws2-005 | PASS | PASS | PASS | PASS |
| ws2-006 | PASS | PASS | PASS | PASS |
| ws2-007 | PASS | PASS | PASS | PASS |
| ws2-008 | PASS | PASS | PASS | PASS |
| ws2-009 | PASS | PASS | PASS | PASS |
| ws2-010 | PASS | PASS | PASS | PASS |
| ws2-011 | PASS | PASS | PASS | PASS |
| ws2-012 | PASS | PASS | PASS | PASS |
| ws2-013 | PASS | PASS | PASS | PASS |
| ws2-014 | PASS | PASS | PASS | PASS |
| ws2-015 | PASS | PASS | fail | PASS |
| ws2-016 | PASS | PASS | PASS | PASS |
| ws2-017 | PASS | PASS | PASS | PASS |
| ws2-018 | PASS | PASS | PASS | fail |
| ws2-019 | PASS | PASS | PASS | PASS |
| ws2-020 | PASS | PASS | PASS | fail |
| ws2-021 | PASS | PASS | PASS | PASS |
| ws2-022 | PASS | PASS | PASS | PASS |
| ws2-023 | PASS | PASS | PASS | fail |
| ws2-024 | PASS | PASS | PASS | fail |
| ws2-025 | PASS | PASS | PASS | fail |
| ws2-026 | PASS | PASS | PASS | PASS |
| ws2-027 | PASS | PASS | PASS | PASS |
| ws2-028 | PASS | PASS | PASS | fail |
| ws2-029 | PASS | PASS | PASS | fail |
| ws2-030 | PASS | PASS | PASS | fail |
| ws2-031 | PASS | PASS | fail | PASS |
| ws2-032 | PASS | PASS | fail | fail |
| ws2-033 | PASS | PASS | PASS | PASS |
| ws2-034 | PASS | PASS | PASS | fail |
| ws2-035 | PASS | PASS | PASS | fail |
| ws2-036 | PASS | PASS | PASS | fail |
| ws2-037 | PASS | PASS | PASS | fail |
| ws2-038 | PASS | PASS | PASS | fail |
| ws2-039 | PASS | PASS | PASS | fail |
| ws2-040 | PASS | PASS | PASS | fail |
| ws2-041 | PASS | PASS | PASS | PASS |
| ws2-042 | PASS | PASS | PASS | fail |
| ws2-043 | PASS | PASS | PASS | PASS |
| ws2-044 | PASS | PASS | PASS | fail |
| ws2-045 | PASS | PASS | PASS | PASS |
| ws2-046 | PASS | PASS | PASS | PASS |
| ws2-047 | PASS | PASS | PASS | PASS |
| ws2-048 | PASS | PASS | PASS | PASS |
| ws2-049 | PASS | PASS | PASS | fail |
| ws2-050 | PASS | PASS | PASS | PASS |

## Discriminativeness verdict

- Rung met: **weak** (weak=True, strong=False)
- v2 is no longer saturated (≥1 hosted pass^3 < 1.000 and the hosted conditions differ on ≥1 task), but the separation is within noise at n=50.
- No observed difference: C1 vs C2 — both conditions identical on this dataset (Δ 0.000).
- Near-miss: C1 vs C3 — Δ pass^3 -0.060 [-0.140, 0.000] (CI touches 0; not decisive at n=50).
- Near-miss: C2 vs C3 — Δ pass^3 -0.060 [-0.140, 0.000] (CI touches 0; not decisive at n=50).
- n=50 honesty: with near-ceiling rates and 50 tasks the intervals are wide; absence of a detectable separation is not evidence of no separation.
