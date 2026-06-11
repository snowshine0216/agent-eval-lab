Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pre-landing parallel review: code-reviewer + report-validity reviewer; one major fix round; empirical re-verification)

## Findings and resolutions

Round 1a (code review): no P0. P1: classify_run could raise AttributeError on stop_reason=parse_failure with a None parse_failure record, violating its "never raises" docstring — FIXED in a819ab4 (None-guard → harness_failure, test-pinned). Notes accepted: AllOf-passing-execution-leg miss lands in other_miss (closed-vocab design); n=2 bootstrap CI degeneracy (guards in place, mooted by the complete rerun); worlds.py empty-tools ValueError (unreachable from parsed datasets).

Round 1b (report-validity review — RISKS, the decisive finding): 24-27 of the 30 local-condition "agent_failure/malformed_reply" runs had NO assistant turn, deterministic 3/3 across tasks — flagged as likely harness-side, with a factually wrong exemplar in the report. Orchestrator root-caused: the client sent no max_tokens; the MLX server's 512-token default truncated the thinking model inside its reasoning channel (27/30 runs at completion_tokens == 512 exactly). An evaluation-system defect misattributed as agent failure — precisely the misclassification this item's deliverable exists to catch. FIXED in a819ab4 / 3116c74 / 3236b3a / 0cca10b:
- explicit completion budget (--max-tokens, default 4096) threaded client→loop→multi_run→CLI, recorded on every trajectory (eval parameter, never a provider default);
- fc-v2: token_budget_exhausted subcategory (never lumped with malformed_reply again), parse_failure None-guard, vocabulary closed at 16 (ADR-0013 version bump);
- local condition rerun under the explicit budget: pass@1 0.133 → 1.000 (45/45; completion tokens 973-4420, median 2310 — the 512 default was binding);
- minimax retried and completed (45/45; replaces the 529-overload partial);
- report regenerated under fc-v2 with the defect narrative, corrected artifact-quoted exemplars, budget-asymmetry limitation, cr-007/cr-014 fc design note, saturation takeaways; byte-identical regeneration (sha256 05139448…).

Round 2 (validity re-verification — CLEAN): all per-condition numbers recomputed from raw artifacts (4×45, all 1.000); local passes spot-verified genuine (real write_file patches, no zero-edit passes); narrative verified against the superseded capture in git history (27+3 arithmetic exact); limitations complete; discriminativeness rung "none" mechanically correct (all hosted Δ 0.000); fc-v2 totality verified (16-row closed vocabulary, no escapes).

## Accepted nits / notes
- fc-v2 row-16 catch-all files unknown evidence shapes as agent_failure/other_miss; arguably harness-side — flagged for a future fc-v3 footnote.
- Saturation is disclosed in the discriminativeness verdict and takeaways but not duplicated in the Known-limitations list — cosmetic placement.
- Hosted conditions ran before the explicit-budget change (max_tokens=None recorded); disclosed in the report as a non-binding asymmetry (all 90 hosted runs passed).

Tests after fix round: 664 passed; ruff check + format clean.
