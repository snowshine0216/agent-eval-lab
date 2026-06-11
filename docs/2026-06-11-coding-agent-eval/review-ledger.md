# code_repair_v1 — review ledger (audit view of `metadata.review`)

Regenerable from the dataset; **not** the gate (the gate is `metadata.review` +
`tests/datasets/test_code_repair_v1.py`). One row per task; rubric result
`a-h:PASS` means all eight `cr-rubric-v1` checks passed. Bug class and fixtures
live in `examples/datasets/code_repair_v1_review_fixtures.json`; tiers in
`code_repair_v1_tiers.json`. Hack fixtures are mandatory on `overfit_resistance`
tasks and T4 tasks with visible tests (ADR-0012 breadth proof).

| id | tier | capability | knob | bug class | rubric | evidence / expected-failure rationale |
|----|------|------------|------|-----------|--------|----------------------------------------|
| cr-001 | T1 | visible_test_localization | — | off_by_one | a-h:PASS | Loop skips index 0; failing visible test names the symptom. Regression floor — every frontier model repairs this. Oracle proves first-element and both-ends cases. |
| cr-002 | T1 | visible_test_localization | — | logic_inversion | a-h:PASS | `locked` used un-negated; one-line inversion. Regression floor. Oracle pins all three truth-table rows. |
| cr-003 | T2 | test_comprehension | — | boundary_condition | a-h:PASS | Contract lives only in the visible tests (`band(70) == "C"`); prose never states the rule. Oracle re-proves every boundary inclusive. Occasional misread of the tests-as-spec framing. |
| cr-004 | T2 | test_comprehension | — | type_coercion | a-h:PASS | Tests demand an int; code returns str. Oracle proves arithmetic use and space-stripping. Weaker models patch the test expectation instead of the program — caught by oracle. |
| cr-005 | T2 | visible_test_localization | — | exception_handling | a-h:PASS | `except TypeError` should be `except KeyError`; symptom (escaping KeyError) is named in the failing test. Oracle covers the no-default and falsy-value paths. |
| cr-006 | T2 | cross_file_repair | — | logic_inversion | a-h:PASS | Symptom in `report.py`'s test; fault is the inverted comparison in `filters.py`. First cross-file hop. Oracle pins yesterday/today boundary and report order. |
| cr-007 | T3 | cross_file_repair | fault_distance | boundary_condition | a-h:PASS | Symptom two imports above the fault (`checkout` → `pricing` → `tiers`); `<` vs `<=` on tier limits. Models that patch `checkout.py` or `pricing.py` fail the oracle's inclusive-limit tests. |
| cr-008 | T3 | prose_localization | spec_obliqueness | off_by_one | a-h:PASS | Prose-only (no visible tests, suite `no_tests`): floor division drops the partial final page. Models must map a user report to ceil-division; oracle proves 11/5→3 and the exact-multiple regression. |
| cr-009 | T3 | prose_localization | spec_obliqueness | aliasing_mutation | a-h:PASS | Prose-only: in-place `sort` mutates the caller's list while output is correct — the result-looks-right trap. `OnlyModifies(files.window.py)` policy leg scopes the edit (guard-checked). |
| cr-010 | T3 | regression_preservation | oracle_breadth | exception_handling | a-h:PASS | Tempting fix `amount >= balance: raise` passes the visible suite but breaks the oracle's exact-balance regression (`withdraw(50, 50) == 0`); zero/negative guards also oracle-protected. |
| cr-011 | T3 | overfit_resistance | oracle_breadth | boundary_condition | a-h:PASS | Visible tests pin only 1900/2023/2024; hack special-cases 1900 and passes them. Oracle (2100, 1800, 2000, 1600, 1996) catches the hack — breadth proven, not claimed. |
| cr-012 | T3 | visible_test_localization | distractor_file | logic_inversion | a-h:PASS | `levels.py` is the named distractor (correct as shipped); fault is the inverted filter in `logfilter.py`. Oracle regression-pins the severity table, so editing the red herring is a gradeable wrong path. |
| cr-013 | T4 | overfit_resistance | multi_hunk | logic_inversion | a-h:PASS | Two inverted comparisons must both flip; hack special-cases the visible ballots and is caught by the oracle's fresh counts. `NoToolCall(run_tests)` leg forces repair-from-reading (secondary to the multi_hunk knob). |
| cr-014 | T4 | regression_preservation | constraint_budget | aliasing_mutation | a-h:PASS | Shared module-level cart dict; the tempting reset-in-place fix passes the visible suite (hack fixture) but breaks the oracle's two-live-carts independence tests. `MaxToolCalls(8)` ≤ `max_steps` 10 (coherence-checked). |
| cr-015 | T4 | overfit_resistance | oracle_breadth | type_coercion | a-h:PASS | Visible tests use only `pens, 12` / `ink, 30`; hack special-cases that row. Oracle demands int amounts for arbitrary and negative rows — `int(amount)` is the only surviving fix. |

## Coverage roll-up (enforced mechanically)

- Tiers: T1=2, T2=4, T3=6, T4=3 (60% T3+T4).
- Capabilities: visible_test_localization ×4, test_comprehension ×2,
  cross_file_repair ×2, prose_localization ×2, regression_preservation ×2,
  overfit_resistance ×3 — all six ≥ 2.
- Bug classes: off_by_one ×2, logic_inversion ×4, boundary_condition ×3,
  type_coercion ×2, exception_handling ×2, aliasing_mutation ×2 — all six ≥ 1.
- Knobs (T3/T4 only): fault_distance, spec_obliqueness ×2, oracle_breadth ×3,
  distractor_file, multi_hunk, constraint_budget.
- Policy compositions: cr-009 `OnlyModifies`, cr-013 `NoToolCall`,
  cr-014 `MaxToolCalls` — three tasks, three constraint types.
- Hack fixtures: cr-011, cr-013, cr-014, cr-015 (every overfit_resistance task
  and every T4 task with visible tests).
