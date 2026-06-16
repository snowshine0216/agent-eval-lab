# Ship-blocked findings — item 001 (pre-push review, /ship steps 8+9)

`/ship` steps 8 (pre-landing: code-reviewer + silent-failure-hunter) + 9 (adversarial)
surfaced findings routed through triage-fix BEFORE opening the PR.

## Must-fix (blocker / latent — wrong data or breaks "never raises")

1. **Administrative-trial leak** (silent-failure-hunter P0; spec §6 violation).
   `marked_failed_not_executed` is honored only in the per-task detail renderer.
   It leaks as a real model failure into three other consumers:
   - `m1_detail.py` `_summary_lines` — cross-model summary prints `0/k ❌`, identical to a real miss.
   - `defects.py` via `valid_by_cond` — administrative non-execution counts toward
     "every condition unanimously fails" → **false task-defect candidate**.
   - `cond_domain_efficiency` via `valid_by_cond` — 0-round/0-token admin run dragged
     into `rounds_median` and stop-reason counts.
   Spec §6: administrative is "administrative 0/k — not executed (owner decision)",
   **never** a real 0-round/0-token failure; excluded from pass^k (D34).

2. **`all_of` leaf `KeyError`** (code-reviewer P1) — `evidence_summary.py` leaf access
   `leaf["passed"]`/`leaf["evidence"]` uses subscript while every other branch degrades
   gracefully; a malformed sub-result raises, breaking the module's "never raises" docstring.

3. **`isinstance(tests, Sequence)` accepts `str`** (code-reviewer + adversarial) —
   `evidence_summary.py` `_node_execution`: a `str` is a `Sequence`; a malformed
   `tests="error"` would crash on the `for name, st in tests` unpack. Guard against str.

4. **Dominant-stop tie-break inconsistency** — `_dominant_stop_reason` (m1_detail) breaks
   count ties toward the lexicographically smallest reason; the m1.py + m1_detail efficiency
   renderers break toward the largest. Same data → two different "dominant stop" values.
   Unify on one rule.

## Accept / note (not blocking — will not affect F/D regeneration)

- Mixed-cap heterogeneous censoring: `cap_bound` from first censored run only (P2). The
  F-ablation uses a frozen uniform cap, so within-group cap heterogeneity won't occur. Accept.
- Duplicate `(task_id, cond)` outcome overwrites the invalid count instead of summing
  (Notes). One outcome per (task, cond) is invariant today. Have the fix sum defensively.
- Fully-void domain → empty subreport with no "voided" note (silent-failure-hunter P1).
  Won't occur for F/D (valid runs present), but spec says "not silently drop" — add a guard.

Resolution: dispatched fix subagent (round 1) to address 1–4 + the void-domain note +
defensive invalid-count sum, all TDD. After green, /ship resumes from step 10 (version bump).
