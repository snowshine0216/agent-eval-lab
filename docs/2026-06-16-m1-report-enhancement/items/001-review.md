Verdict: PASS-WITH-NITS

Source: /ship steps 8+9 (pre-landing review: pr-review-toolkit:code-reviewer + silent-failure-hunter; adversarial review). Blockers/latent bugs were FIXED before the PR was pushed (round-1 fix, commit 94e6c80); only accepted P2 nits remain open.

## Findings (and resolution)

### Fixed before push (were blocker / latent — would have shipped wrong data or broken "never raises")
- **Administrative-trial leak** (silent-failure-hunter P0; spec §6) — `marked_failed_not_executed` honored only in the per-task detail; leaked as a real model failure into the cross-model summary (`0/k ❌`), task-defect candidacy (false unanimous failure), and efficiency aggregation (0-round/0-token run dragging the median). FIXED: `_is_administrative` helper; `real_by_cond` (admin-excluded) feeds `task_defect_candidates` + `cond_domain_efficiency`; summary renders `— admin (not executed)`; admin cells excluded from `shared_failing_units`. (`m1_detail.py`)
- **`all_of` leaf `KeyError`** (code-reviewer P1) — subscript `leaf["passed"]`/`leaf["evidence"]` broke the "never raises" contract. FIXED: `.get` + fall-through to `_unknown`. (`evidence_summary.py`)
- **`isinstance(tests, Sequence)` accepts `str`** (code-reviewer + adversarial) — a malformed string `tests` would crash the unpack. FIXED: guard `isinstance(tests, (list, tuple))`. (`evidence_summary.py`)
- **Dominant-stop tie-break inconsistency** — `_dominant_stop_reason` (smallest) vs efficiency renderers (largest) → two different "dominant stop" for the same data. FIXED: unified on lexicographically-smallest-among-max across all three sites. (`m1_detail.py`, `m1.py`)
- Minor: invalid-counts now summed across multiple outcomes; void-domain emits an explicit note.

14 regression tests added for the above; full report suite green.

### Accepted nits (P2 — not blocking; do not affect F/D regeneration)
- `cap_bound` displays the first censored run's cap only (mixed-cap groups). The F-ablation uses a frozen uniform cap, so within-group heterogeneity won't occur.
- Latent: a future grader emitting `tests` as a non-list Sequence other than str is unreachable with current node_execution/fact_key graders (both emit list-of-pairs).

Adversarial verdict: RISKS (only P2 after fixes). No open blocker or latent bug.
