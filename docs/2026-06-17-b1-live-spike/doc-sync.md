Verdict: PASS
Subagent: orchestrator (in-prompt, N=1 spec mode — lightweight)
Items reviewed: 1

Doc changes verified:
- CHANGELOG.md — v0.6.0 section covers run-b/report-b + new modules + run_trials_k_valid extraction + file:// guard + candidate folder (commit 6bd8b9f, squash).
- CONTEXT.md — B-spike terms (`definition-match checklist`, `owner verdict`, `censoring`) present, added during the pre-completed grill (commits af52b4b / d536100).
- docs/adr/0021-b-set-spike-grade-is-an-owner-verdict-joined-at-report-time.md — covers the grade-less BTrial / owner-verdict-joined-at-report-time decision.
- docs/2026-06-13-agentic-v1-domains-runs/B1-LIVE-RUNBOOK.md — owner-facing live-run procedure (preconditions, calibrate-first, store relocation, claude budget-cap known limitation).

Missing coverage: none.

Note: `run-b`/`report-b` are intentionally NOT added to README.md — the repo's convention is that per-spike/eval commands are documented in their dated run-docs runbook (as `run-f`/`run-m1` were), while README curates the foundational D-set flows. Following that convention is the correct doc home, not a gap.
