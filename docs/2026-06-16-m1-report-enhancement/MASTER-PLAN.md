# MASTER-PLAN — M1 report enhancement

- **Mode:** `spec` (N = 1)
- **Project type:** `non-web` (Python eval-lab CLI / library; reports are markdown → post-ship verifier is `/verify`, never `/qa`)
- **PR shape:** A (per-item PR; no `--rollup` in invocation)
- **Feature branch (base for the item PR):** `claude/fervent-panini-498c1a` (current worktree branch — non-protected, at `main` HEAD)
- **Item sub-branch:** `claude/m1-report-enhancement-001`
- **Default / protected base:** `main` — NOT an auto-merge target. Item PR lands into the feature branch; Phase 3 opens a feature→`main` PR for the user (left unmerged).

## Per-mode skill skips (spec mode)

| Phase | Skill | Status this mode |
|-------|-------|------------------|
| spec (brainstorming) | `superpowers:brainstorming` | ⏭️ SKIPPED — user authored the spec (copied verbatim to `items/001-spec.md`) |
| grill | `grill-with-docs` | ⏭️ PRE-COMPLETED — user-grilled (source spec records a CONTEXT-grounded grilling pass, Q1–Q6). Orchestrator MUST NOT auto-invoke. |
| plan | `superpowers:writing-plans` | ✅ RUNS — Opus subagent (ENTRY phase) |
| impl | `superpowers:subagent-driven-development` | ✅ RUNS — Sonnet |
| drift | in-prompt logic | ✅ RUNS — Sonnet |
| ship | `/ship` (PR + docs + inline review) | ✅ RUNS |
| verify | `/verify` (non-web branch of post-ship XOR; never `/qa`) | ✅ RUNS — Sonnet |
| pr-review | `/code-review` on open PR | ✅ RUNS — Sonnet |
| fix | triage subagent consuming the 3 post-ship verdicts | conditional |
| merge | `gh pr merge --squash --delete-branch` (Mode A) | ✅ RUNS |

## Loop exit contract (item 001)

Merge only when all three post-ship verdicts are PASS / PASS-WITH-NITS:
1. `items/001-verify.md` — `^Verdict: PASS` (non-web entry-point smoke)
2. `items/001-review.md` — PASS / PASS-WITH-NITS (captured inline by `/ship` steps 8+9)
3. `items/001-pr-review.md` — PASS / PASS-WITH-NITS (`/code-review` on the PR)

Plus presence of `items/001-spec.md`, `items/001-plan.md`, and `items/001-drift.md` (`^Verdict: PASS`). Grill verdict absence is OK in spec mode (PROGRESS ⏭️).

## Key constraints carried from the source spec

- **Report-layer only.** No edits to runner, scoring, `grade.passed`, pass^k, CI, or comparison math.
- **TDD mandatory** (source spec §10 lists the test files first). Determinism test asserts byte-identical output.
- **Two derivation sources kept separate:** `evidence_gap` reads `GradeResult` (oracle units, `displaced_paths`); `edit_paths` reads `Trajectory` (edit-tool targets, `out_of_scope`). Must not merge (CONTEXT.md distinction).
- **`defects.py` extract** from `final.py` is a pure extract-and-import refactor — `final.py`'s existing tests must stay green (no behavior change).
- **Heading rename** `Failure taxonomy → Failure classification (fc-v4) per condition` at `m1.py:374`; update assertion at `tests/reports/test_m1_render.py:70`.
- **CLI:** `report-m1` gains `--subreports/--no-subreports` (default on) + optional `--subreport-dir`; subreports written to the same dir as `--out`.

## Final regeneration (Phase 3, user request)

Run data lives in the **gitignored** `reports/agentic-v1/` (local-only; present in the main checkout, copied into the worktree for the run). Available:
- **F:** deepseek, glm, minimax, siliconflow Qwen3.5-397B-A17B, siliconflow Qwen3.6-35B-A3B (`runs-m1-*-F.jsonl`)
- **D:** deepseek, minimax (`runs-m1-*-D.jsonl`)

`report-m1 --spec <frozen ExperimentSpec> --runs DOMAIN:condition_id=path … --prices <prices> --out <overview.md>` → writes overview + `M1-F-report.md` + `M1-D-report.md`. Surface all three for review.
