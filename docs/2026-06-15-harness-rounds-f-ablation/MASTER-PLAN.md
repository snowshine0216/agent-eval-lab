# MASTER-PLAN — harness-rounds-f-ablation (infra)

- **Mode:** backlog
- **Project type:** non-web   → post-ship verifier = `/verify` (XOR; never `/qa`)
- **PR shape:** A   (per-item PRs into the feature branch; no `--rollup`)
- **Feature branch:** `autodev/harness-rounds-f-ablation-feature` (synthesized off `main`)
- **Base for sub-PRs:** `autodev/harness-rounds-f-ablation-feature` (NOT `main`; `main` is protected, no opt-in given)
- **Sub-branch prefix:** `claude/harness-rounds-f-ablation-<id>`
- **Item order:** 001, 002, 003, 004, 005, 006   (locked from design Part G — frozen reviewed sequence)
- **Token ceiling:** 1.5M (soft). Stop + confirm with user if approached. See cost note below.

## Per-mode skill skips (user override — 2026-06-15)

The user explicitly instructed **skip brainstorming + grill per item** (design is locked: 3
adversarial pre-spec rounds + grilling pass; ADR-0016/0017 + glossary already written). This is a
valid in-turn override of the backlog-mode default (SKILL.md → "Instruction priority").

| Phase | Status this run | Note |
|-------|-----------------|------|
| spec (brainstorming) | **skipped subagent** — `spec.md` authored by orchestrator **extraction** of the design sections listed in MASTER-SPEC.md | column shows ✅ when the extract exists with Goal + Acceptance |
| grill (grill-with-docs) | **⏭️ skipped** | ADRs/glossary already written in the design's grilling pass; run-level doc-sync (Phase 3) catches any gap |
| plan (writing-plans) | **runs — Opus** | plans are the source of truth; kept on Opus despite N≥5 (rigor) |
| impl / drift / verify / pr-review / fix | **runs — Sonnet** | standard |

**Run-level exit-contract adjustment:** backlog mode normally requires `items/<id>-grill.md` per
item. Waived here by the user override — grill is ⏭️. All other verdict files (drift, ship,
verify, review, pr-review) are still mandatory per item.

## Dependency scan

**Skipped** — design Part G is already the reviewed, frozen dependency sequence. Order locked
directly (see MASTER-SPEC.md → "Item-order rationale"). Not a heuristic "smallest first": it is the
authoritative sequence the design authors froze.

## Cost note (N = 6 ≥ 5)

Per item ≈ 1 Opus (plan) + ~4–5 Sonnet (impl, drift, verify, pr-review, ≥0 fix) + indirect `/ship`
(~2 review subagents) + `/code-review` (~5 Sonnet + ~5 Haiku). 6 items ≈ **~36 direct dispatches**.
Brainstorming + grill skipped removes ~12 Opus dispatches vs the full backlog contract. Projected
**~1–1.5M tokens**. No `Sonnet override` on plan (kept Opus for plan quality).

## Protected-branch posture

`main` is protected; no opt-in phrase in the invocation → **nothing auto-merges to `main`**.
All sub-PRs target the feature branch. Phase 3 opens (not merges) a feature→`main` PR as a review
surface and leaves it for the user.

## Verifier mapping

Non-web → every item's post-ship verifier is `/verify` (entry-point smoke with evidence). The
library-with-no-entry escape hatch applies to pure-plumbing items that add no CLI surface
(e.g. 001/002 internal changes) — `/verify` records the unit-test + report re-emit evidence instead.
