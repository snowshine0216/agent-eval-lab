# PROGRESS — harness-rounds-f-ablation (infra)

Mode: backlog · Project type: non-web · PR shape: A · Feature branch: `autodev/harness-rounds-f-ablation-feature`

Legend: ⏳ pending · 🔄 in-progress · ✅ done · ⚠️ soft-fail (fix loop) · ⏭️ skipped · ⛔ refused gate

| id | spec | grill | plan | branch | impl | drift | PR | verify | review | pr-review | fix | merge |
|----|------|-------|------|--------|------|-------|----|--------|--------|-----------|-----|-------|
| 001 | ✅ | ⏭️ | ✅ | ✅ `claude/harness-rounds-f-ablation-001` | ✅ `2fd47fb` | ✅ `items/001-drift.md` | 🔄 | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 002 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 003 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 004 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 005 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 006 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

**Column note:** this is a **non-web** run, so the post-ship XOR resolves to **verify** (no `qa`
column). `grill` is ⏭️ for every item per the user's authoring override (MASTER-PLAN.md). `spec` is
authored by extraction (brainstorming subagent skipped) — ✅ means the extract exists with
Goal + Acceptance.

## Item titles
- **001** — fc-v4 classifier + pass^k censoring + re-emit reports (Part G step 1)
- **002** — `max_rounds` plumbing + recorded policy fields (Part G step 2)
- **003** — Arm-as-task + Factor P (Part G step 3)
- **004** — Candidate-tree enrichment + visible/held-out curation (Part G step 4)
- **005** — Factor V confined-execution sandbox (Part G step 5)
- **006** — `run-f-ablation` driver + freeze `f_ablation_spec` (Part G step 6, code only)

## Run-level (Phase 3)
| gate | status |
|------|--------|
| run-doc-sync | ⏳ |
| run-final-verify | ⏳ |
| run-close-out | ⏳ |

## Log
- 2026-06-15 — Intake: mode=backlog, non-web, PR shape A. User-locked scope (infra, steps 1–6 code;
  paid run + report deferred) and authoring (skip brainstorm+grill). Synthesized feature branch
  `autodev/harness-rounds-f-ablation-feature` off `main` (main protected, no opt-in). Design
  artifacts (spec, ADR-0016, ADR-0017, CONTEXT.md glossary, uv.lock version sync) committed as run setup.

## Final status block (filled at close-out)
- Feature branch: `autodev/harness-rounds-f-ablation-feature`
- Merged into protected branch: no (left open for user review)
