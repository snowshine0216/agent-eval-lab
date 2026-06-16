# MASTER-SPEC — Per-domain round caps + F-set harness-factor ablation (infra)

- **Mode:** backlog (6 IN-scope items = Part G steps 1–6 *code*)
- **Project type:** non-web (Python eval lab, pytest) → post-ship verifier is `/verify`
- **Source design:** [docs/superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md](../superpowers/specs/2026-06-15-agentic-v1-harness-rounds-F-ablation-design.md)
- **Run scope (user-locked 2026-06-15):** *Infra only — Part G steps 1–6 code.* Build all
  classifier/scoring/plumbing/ablation infrastructure **including** the `run-f-ablation` driver
  and frozen `f_ablation_spec`, but **stop before any paid provider execution**. The pilot + full
  240-attempt run and the descriptive report are deferred (real, irreversible API spend).
- **Authoring (user-locked):** per item, **skip brainstorming + grill** — the design survived 3
  adversarial pre-spec review rounds + a CONTEXT-grounded grilling pass (ADR-0016/0017 + glossary
  written inline). Each item's `spec.md` is authored by **extraction** of the relevant design
  sections; `plan.md` is authored by Opus `writing-plans`.
- **PR shape:** A (per-item PRs into the synthesized feature branch).

The design's **Part G is the frozen, reviewed dependency sequence** — item order is locked from it
directly (no separate dependency-scan dispatch).

---

## IN-scope items (6) — Part G steps 1–6 (code)

| id | Part G step | Title | Design sections | Network? |
|----|-------------|-------|-----------------|----------|
| 001 | 1 | **fc-v4 classifier + pass^k censoring + re-emit reports** | Part E (fc-v4 rows 1–4), §D.1 (censoring), §8.8 | none — re-run `reports/m1.py` over existing JSONL; verified **0 pass^k moves** |
| 002 | 2 | **`max_rounds` plumbing + recorded policy fields** | Part A (A.1/A.2/A.3), §9.2, §D.3 (resource vs time split, `n_censored`), §11.2/§11.3, ADR-0017 | none — TDD w/ stub loop |
| 003 | 3 | **Arm-as-task + Factor P** | §B.1, §B.2 (arm = distinct `task_id`; task-scope `run_uid`), §B.3 (Factor-P prompt block), §11.1/§11.4/§11.8 | none |
| 004 | 4 | **Candidate-tree enrichment + visible/held-out curation** | §B.5 (context-set enrichment), §10.4 (overlay-disjointness invariant + unit test), §11.6, §C (per-subset enrichment) | none |
| 005 | 5 | **Factor V confined-execution sandbox** | §B.4 (seatbelt `sandbox-exec`, `runners/sandboxed_node_edge.py`, `make_authored_test_executor`, tail-aware feedback rendering), §9.1/§10.3, ADR-0016, §11.5 | none (Darwin-gated; CI injects fake executor) |
| 006 | 6 (code only) | **`run-f-ablation` driver + freeze `f_ablation_spec`** | §B.6 (roster/size), §B.7 (`ablation_run_order` pure fn + driver + realized-order sidecar), §11.9, §G6 | **driver + spec + unit tests only — NO pilot, NO full run** |

### Item-order rationale (locked from Part G)
`001 → 002 → 003 → 004 → 005 → 006`. Strictly sequential as the design sequences it:
- 002 introduces `max_rounds_bound`/`max_rounds` stop literal; 001's censoring reads them
  defensively (`getattr(..., False)` for old records) so 001 can land first per Part G with 0 moves.
- 003 (arm-as-task) consumes the recorded policy fields from 002 and the F task machinery.
- 004 enriches the trees the 003 arms share; 005's V loop learns from those trees.
- 006 orchestrates 003–005 into the seeded run order.

---

## OUT-scope items (deferred → SKIPPED.md)

| step | Title | Reason |
|------|-------|--------|
| 6 (execution) | Pilot (≈24) + full **240-attempt** paid run across 4 frontier models, macOS-local | User-deferred this run; real irreversible API spend. Driver/spec built (item 006) so the user can trigger it. |
| 7 | Descriptive report (Part C narrative + §D.2/§D.3/§D.4 report) + queue F4–F6 | Needs results from the deferred run. §D.4 harness signals (`product_edit_count`, `authored_test_edit_count`, `out_of_scope_edit_rate`, `run_tests` adoption) compute over run records. |
| Part F | Held-out F4–F6 confirmation | Already declared a separate follow-up phase in the spec (§F); out of scope here beyond the queue note. |

No silent omissions: every Part of the design maps to an IN item or an OUT row above
(Part D.1→001, D.3→002, D.2/D.4→step 7 OUT; Part C enrichment→004, C report-narrative→step 7 OUT).
