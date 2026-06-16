# Item 001 — fc-v4 classifier + pass^k censoring + re-emit reports

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override, 2026-06-15). Authoritative source: **Part E** (fc-v4) + **§D.1** (pass^k censoring) +
> **§8.8** of
> [2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md](../../superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md).
> This is Part G **step 1** and lands **first** (no network; re-runs reports over existing JSONL).

## Goal

Correct two already-declared-but-unenforced contracts in the reporting layer, bumping the classifier
version per ADR-0013, **without moving any historical `pass^k` number**:

1. **Classifier fc-v3 → fc-v4** ([reports/classify.py](../../../src/agent_eval_lab/reports/classify.py)):
   three semantic row changes so failing node-F runs and budget-capped runs land in honest buckets.
2. **`pass^k` honors its declared `censoring_policy="failure"`**
   ([metrics/reliability.py](../../../src/agent_eval_lab/metrics/reliability.py)): a run counts as a
   pass only if it both graded-passed **and** was not budget-capped.

Re-emit the M1 reports over existing JSONL to demonstrate the **taxonomy outputs move (the fix) but
`pass^k` does not** (verified blast radius below).

## Acceptance criteria

**fc-v4 classifier (Part E):**
- [ ] `CLASSIFIER_VERSION = "fc-v4"` (was `"fc-v3"`).
- [ ] **Row E.1 — `node_execution` leaf fix:** `first_execution_evidence`
  ([classify.py:104](../../../src/agent_eval_lab/reports/classify.py:104)) accepts a
  `"node_execution"` grader_id (today only `"execution"`), so a failing node-F run classifies as
  `agent_failure / oracle_red` instead of the catch-all `other_miss`. Verified by a test over a
  real node-F failing record's evidence shape.
- [ ] **Row E.2 — budget-override reconciliation:** the budget override fires on the loop's **real**
  stop reasons — `max_steps` (legacy) **+ `safety_cap` + `max_rounds`** — not only `max_steps`
  ([classify.py:300](../../../src/agent_eval_lab/reports/classify.py:300) today keys on `max_steps`
  alone, which the loop emits rarely). A cap-bound run lands in the budget bucket.
- [ ] **Row E.3 — row-1 cap-bound guard:** `classify_run`'s `if run.grade.passed` short-circuit
  ([classify.py:135](../../../src/agent_eval_lab/reports/classify.py:135)) is guarded with
  `and not cap_bound`, so a run that graded-passed **but was budget-capped** classifies as
  `budget_exhausted` (NOT `passed`) — consistent with §D.1.
- [ ] Each changed/added taxonomy row has a unit test; the classifier stays **pure / total / never
  raises** (the existing fc-v3 invariants hold).
- [ ] **ADR-0013 amended** with an fc-v4 entry (version bump rationale + the three row changes).

**pass^k censoring (§D.1):**
- [ ] `pass_pow_k` ([reliability.py:26](../../../src/agent_eval_lab/metrics/reliability.py:26)) and
  `task_reliability` ([reliability.py:56](../../../src/agent_eval_lab/metrics/reliability.py:56))
  count a run as a pass **iff** `grade.passed AND NOT (safety_cap_bound OR max_rounds_bound)`.
- [ ] The bootstrap-CI helpers (`pass_pow_k_bootstrap_ci`, `paired_pass_pow_k_diff_ci`) inherit the
  censor automatically because they route through `task_reliability` — confirm, don't re-implement.
- [ ] **Defensive `max_rounds_bound` read:** `max_rounds_bound` does **not exist on records yet**
  (it arrives in item 002). The censor MUST read it defensively (e.g. `getattr(..., False)` or via a
  records helper that defaults `False`) so item 001 lands standalone and old records (no field) are
  unaffected. `safety_cap_bound` already exists
  ([trajectory.py:76](../../../src/agent_eval_lab/records/trajectory.py:76), round-tripped in
  serialize, summed in aggregate).

**Re-emit + verified blast radius (§D.1 / §8.8 / Part G step 1):**
- [ ] Re-run the M1 report path (`reports/m1.py`) over existing JSONL.
- [ ] **Zero `pass^k` numbers move:** of 1,360 historical records, 0 have
  `grade.passed=True AND safety_cap_bound=True`; the 5 `safety_cap` + 1 legacy `max_steps` runs
  already failed on grade. Demonstrate this empirically (a check/test over the committed JSONL), so
  enforcing the censor is provably a no-op on existing pass^k.
- [ ] Taxonomy outputs **do** move where the fc-v4 rows changed (node-F failures, cap-bound runs).

## Non-goals
- **No `max_rounds` plumbing** — the loop/trajectory/serialize/config work for `max_rounds` is
  **item 002**. Item 001 only *reads* `max_rounds_bound` defensively; it does not produce it.
- **No ablation, no arm-as-task, no Factor P/V** (items 003–006).
- **No change to the frozen oracle output contract** (ADR-0009) — untouched.
- **No new domains** — the censor is intentionally global (§10.6 / §D.1); D/B inherit it by design
  (forward consequence stated in §D.1). Do not scope it to F.
- Do **not** broaden `pass_at_1` censoring unless the plan finds it strictly required — §D.1 governs
  `pass_pow_k` / `task_reliability` only.

## Constraints
- **Functional-programming / TDD house style** (CLAUDE.md): pure functions, immutability, tests
  first. The classifier is already "pure, total, never raises" — preserve that.
- **ADR-0013** mandates a version bump for any semantic row change → fc-v4 (the amendment is part of
  this item, not optional).
- Classifier output is **derived, never stored** — no record-schema change in this item.
- Censor must be **backward-compatible**: records lacking `max_rounds_bound` (all of them, today)
  classify exactly as before except for the already-failing cap-bound runs.
- Re-emit step is **offline** — no provider/network calls.
