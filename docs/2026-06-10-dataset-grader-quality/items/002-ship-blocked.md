# Ship-blocking findings (steps 8+9 review) — round 1

P0 — ws2-047 no-op false PASS: final_state asserts a value already present in
initial_state; trajectory leg is purely negative → zero-tool agent PASSes a T4
task, inflating constraint_compliance pass^k. Fix the task (positive
tool_call_match leg) + add a conformance check killing the whole class
(every task's verification must not be pre-satisfied by initial_state).

P1 — _is_state_dependent uses substring matching ("T-1" in "T-10...") → fragile
proxy. Word-boundary regex.

P1 — test_distractors_never_expected check (3) loop has no assertion (vacuous).

P1 — layered_constraint state-dependent tasks (ws2-044, ws2-049) invisible to
the anti-rote proxy → future rote-ification undetected.

Noted, no change: exact_sequence extra-call strictness is by-design (over-calling
is a graded failure mode; multiset would not change extra-call behavior);
find_account empty-candidates=success is documented search semantics;
grade_final_state ignoring initial_state is locked path-independent outcome
semantics — preservation constraints ("T-2 stays open") are legitimate, so
pre-satisfaction is a DATASET defect, policed by the new conformance check.
