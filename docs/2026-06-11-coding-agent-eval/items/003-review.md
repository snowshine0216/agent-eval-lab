Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pre-landing parallel review: code-reviewer on dataset quality + dedicated hack-resistance reviewer; one fix round; empirical re-verification)

## Findings and resolutions

Round 1a (dataset-quality review): no P0. P1s fixed in 336805b: cr-006 calendar-pinned oracle dates ("2026-06-10/11" → neutral past dates, test names de-relativized); cr-015 reference solution explicit int(amount.strip()). Positive findings: no-op conformance check is real grading (not tautological); cr-010 regression trap genuinely discriminates; cr-013 NoToolCall/no-op interaction correct; sidecars/ledger internally consistent.

Round 1b (hack-resistance review — BREAKS): empirically verified oracle-breadth defects — special-casing the oracle's narrow inputs passed cr-008, cr-011, cr-009 (and structurally cr-001/cr-002/cr-013) while leaving the bug intact. Triage note (threat model): oracle tests are held out — an agent cannot read oracle inputs, so direct hardcoding is not agent-reachable; the defects matter as (a) measurement validity (a partially-wrong fix could pass) and (b) contradiction of the overfit_resistance label's mechanical claim (ADR-0012). FIXED in 336805b + 77fa3dd: oracles broadened (cr-001→6, cr-002→5, cr-008→11, cr-009→7 with multi-input not-mutated asserts, cr-011→13, cr-013→9 with boundary-equality cases); hardcode-style hack fixtures added for all six and wired into the conformance suite; ledger rows re-stamped under cr-rubric-v1.

Round 2 (hack-resistance re-verification — CLEAN): all three prior exploits now rejected through the production oracle edge; new cheapest-edit attempts per task rejected (XOR hack on cr-002 caught by the added (F,T) case; boundary flips on cr-013 caught; hardcoding cr-001 now needs 8 branches vs a 1-line genuine fix). Genuine fixes pass; conformance 32/32.

## Accepted nits / notes
- Hack fixtures remain null for cr-003/004/005/007/010/012/014-015 reference-style rows where the conformance suite's other invariants (stub-tree rejection, disjointness, breadth via the fixed tasks) cover the realistic hacks; revisit when Weeks 13-14 generation scales the dataset.
- Conformance runtime 6.96s of the 120s budget (~83 sandbox runs + broadened oracles).

Tests after fix round: 582 passed; ruff clean.
