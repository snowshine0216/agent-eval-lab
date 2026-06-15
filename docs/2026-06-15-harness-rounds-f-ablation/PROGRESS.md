# PROGRESS — harness-rounds-f-ablation (infra)

Mode: backlog · Project type: non-web · PR shape: A · Feature branch: `autodev/harness-rounds-f-ablation-feature`

Legend: ⏳ pending · 🔄 in-progress · ✅ done · ⚠️ soft-fail (fix loop) · ⏭️ skipped · ⛔ refused gate

| id | spec | grill | plan | branch | impl | drift | PR | verify | review | pr-review | fix | merge |
|----|------|-------|------|--------|------|-------|----|--------|--------|-----------|-----|-------|
| 001 | ✅ | ⏭️ | ✅ | ✅ `claude/harness-rounds-f-ablation-001` | ✅ `2fd47fb` | ✅ `items/001-drift.md` | ✅ [#26](https://github.com/snowshine0216/agent-eval-lab/pull/26) | ✅ `items/001-verify.md` | ✅ `items/001-review.md` PASS-WITH-NITS | ✅ `items/001-pr-review.md` PASS-WITH-NITS | ✅ 0 rounds | ✅ `a2a4be1` |
| 002 | ✅ | ⏭️ | ✅ | ✅ `claude/harness-rounds-f-ablation-002` | ✅ `7a5e822` | ✅ `items/002-drift.md` | ✅ [#27](https://github.com/snowshine0216/agent-eval-lab/pull/27) | ✅ `items/002-verify.md` | ✅ `items/002-review.md` PASS-WITH-NITS (1 fix round) | ✅ `items/002-pr-review.md` PASS-WITH-NITS | ✅ 1 round | ✅ `420cc69` |
| 003 | ✅ | ⏭️ | ✅ | ✅ `claude/harness-rounds-f-ablation-003` | ✅ `d43f5e1` | ✅ `items/003-drift.md` | ✅ [#28](https://github.com/snowshine0216/agent-eval-lab/pull/28) | ✅ `items/003-verify.md` | ✅ `items/003-review.md` PASS-WITH-NITS (pre-push fix round) | ✅ `items/003-pr-review.md` PASS-WITH-NITS | ✅ 1 round (2 nits) | ✅ `40e4f26` |
| 004 | ✅ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 005 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 006 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

**Column note:** this is a **non-web** run, so the post-ship XOR resolves to **verify** (no `qa`
column). `grill` is ⏭️ for every item per the user's authoring override (MASTER-PLAN.md). `spec` is
authored by extraction (brainstorming subagent skipped) — ✅ means the extract exists with
Goal + Acceptance.

## ⏸ PAUSED at 2/6 — resume guide (next session)

**Status:** items 001 + 002 merged into the feature branch; items **003–006 not started**. Paused at
the user's request (2026-06-15) to resume in a fresh session. Feature branch is clean, green
(1021 passed / 17 skipped), pushed; no leftover (secret + stray `learning/` removed & gitignored).

**To resume** (the run is resumable from disk — `.autodev-current` points here):
1. `git switch autodev/harness-rounds-f-ablation-feature && git pull` (head was `b69e403`).
2. Re-invoke `/autodev docs/2026-06-15-harness-rounds-f-ablation` (or continue manually). Mode=backlog,
   non-web, PR shape A, skip brainstorm+grill per the original user override (see MASTER-PLAN.md).
3. Next item = **003** (Arm-as-task + Factor P). Then 004 (tree enrichment), 005 (V seatbelt sandbox —
   security-sensitive, macOS-only), 006 (run-f-ablation driver + frozen f_ablation_spec). Item order
   is locked in MASTER-PLAN.md from design Part G. Step-6 paid execution + step-7 report stay OUT
   (SKIPPED.md).
4. Per-item loop: extract spec → Opus plan → branch `claude/harness-rounds-f-ablation-00N` → Sonnet
   impl → drift → /ship (base=feature, **stage only own files — no broad `git add`**) → /verify +
   /code-review → fix → squash-merge → sync local feature.
5. **Carry-forward into item 003+ planning:** none open from 002 (CF1/CF2 retired). Watch the F
   resolver-bypass note (002-review.md) — item 003 introduces F task-arms, so revisit whether per-task
   F `max_rounds` should route through `resolve_max_rounds`.

**⚠️ Action for the user:** rotate the OpenRouter API key that was in `.env.bak.1781491343` (push
protection blocked it; never reached GitHub, but it was committed locally then purged).

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
- 2026-06-15 — **Item 003 MERGED** (PR [#28](https://github.com/snowshine0216/agent-eval-lab/pull/28)
  squash → `40e4f26`). Arm-as-task + Factor P: 12 F task-arms (3×4) as distinct `task_id`s (M2
  pattern), Factor-P prompt block in `make_edit_task` (gated by `initial_state["factor_p"]`),
  task-scoped `run_uid`; V tool surface declared with executor deferred to 005 (NotImplementedError
  live-guard); no `arm_id`/spec change (frozen M1 specs still verify). v0.2.3; 1033 tests green;
  ruff check+format clean whole-repo. **Ship steps 8+9 caught a latent P0** (`build_candidate_tree`
  F3 dispatch missed armed ids → would corrupt F3 arm scores) + CI-red `ruff check` on new tests
  (and 2 pre-existing E501s from 002) → fixed pre-push (`8900c1f`). pr-review PASS-WITH-NITS (4 nits;
  2 fixed, 2 accepted). **Resume next = item 004** (candidate-tree enrichment + overlay-disjointness).
- 2026-06-15 — **Resumed** from pause (fresh session). Items 003–006 picked up; 003 done.
- 2026-06-15 — **PAUSED at 2/6 per user.** Feature branch `autodev/harness-rounds-f-ablation-feature`
  clean + green (1021 passed) at `b69e403`, left open (NOT merged to main — only 2/6 done, no opt-in).
  Untracked + gitignored stray `learning/` study artifacts swept in by a broad `git add`. Resume guide
  above. Items 003–006 not started.
- 2026-06-15 — Intake: mode=backlog, non-web, PR shape A. User-locked scope (infra, steps 1–6 code;
  paid run + report deferred) and authoring (skip brainstorm+grill). Synthesized feature branch
  `autodev/harness-rounds-f-ablation-feature` off `main` (main protected, no opt-in). Design
  artifacts (spec, ADR-0016, ADR-0017, CONTEXT.md glossary, uv.lock version sync) committed as run setup.
- 2026-06-15 — **Item 002 MERGED** (PR #27 squash → `420cc69`). max_rounds turn-bound + recorded
  policy fields; v0.2.2; 1021 tests green; CF1/CF2 retired. Review found+fixed 2 latent bugs (dset_run
  safety_cap thread; env_unhealthy override incl. max_rounds) in 1 fix round; pr-review PASS-WITH-NITS.
  ⚠️ **SECURITY:** impl step's broad `git add` swept `.env.bak.1781491343` (OpenRouter key) into a
  commit; **push protection blocked it — never reached GitHub**; branch history rewritten to purge it;
  `.env.bak*`/`*.bak` gitignored. **User should rotate that OpenRouter key.** For items 003–006, impl
  subagents instructed to stage only their own files (no broad `git add`).
- 2026-06-15 — **Item 001 MERGED** (PR #26 squash → `a2a4be1`). fc-v4 classifier + pass^k censoring;
  993 tests green; 0 pass^k moves verified; v0.2.1. Review PASS-WITH-NITS, verify PASS, pr-review
  PASS-WITH-NITS, fix 0 rounds. **Carry-forward to 002:** serialize.py must round-trip
  `max_rounds_bound` (else capped runs silently deserialize uncapped) + swap defensive `getattr` for a
  real field (CF1/CF2 in `items/001-review.md`).

## Final status block (filled at close-out)
- Feature branch: `autodev/harness-rounds-f-ablation-feature`
- Merged into protected branch: no (left open for user review)
