# Item 003 — Verify (F3 oracle discrimination)

**VERDICT: PASS** · 2026-06-13 · branch `feat/agentic-v1-003-f3-oracle` · node v22.22.2

Independently re-run through the oracle (`build_f3_verification` → node `--test` edge):

| Candidate `report-to-allure.js` | F3 attachment test | Causal guard (correlate/signal) | Oracle verdict |
|---|---|---|---|
| **golden** (fix applied) | PASS 35/35 | PASS 57/57 | **PASS** ✅ |
| **pre-fix base** `5b0c13a6` | FAIL 33/35 (2 non-2XX subtests) | PASS | **FAIL** ✅ (correctly fails the bug) |
| **surfaces-2xx mutant** (`status >= 600`) | FAIL | FAIL | **FAIL** ✅ (contradiction check) |
| **causal-tamper** (signal.js broken) | PASS | FAIL | **FAIL** ✅ (D31 guard) |

- **Env-free + deterministic** (§6): no live server; node-test over recorded fixtures.
- **Contradiction checks (§18.6):** a 2xx surfacing → fail; dropping the 503 → fail; ≥3 fixtures (golden test cases).
- **D31:** causal layer (correlate/signal) asserted unchanged by a second `NodeExecutionSpec` in the `AllOf`.
- **D19 no-leak:** `test_build_f3_does_not_leak_golden_source_into_held_out` PASS — only the golden TEST is overlaid from the evaluator store; the golden SOURCE never enters a candidate-visible tree.
- Full suite **799 passed** with node-22 (8 node-gated tests skip cleanly without node); ruff clean; web-dossier + evaluator-only untouched.
