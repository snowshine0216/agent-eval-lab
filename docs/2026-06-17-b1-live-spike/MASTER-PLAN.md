# MASTER-PLAN — B-1 Live Spike

- **Mode:** spec
- **Project type:** non-web   <!-- Python CLI/eval-harness package (src/agent_eval_lab). Post-ship verifier = /verify (NOT /qa). -->
- **PR shape:** A (per-item PRs into the feature branch; no `--rollup` in the invocation)
- **Feature branch:** `feat/b-set-live-spike` (current, non-protected — sub-branch PRs land here; left open at end for the owner)
- **Default/base branch:** `main` (protected — never auto-merged; no opt-in given this turn)
- **Item order:** single item `001` (N=1)
- **Sub-branch:** `claude/b1-live-spike-001`

## Per-mode skill skips (spec mode)

| Phase | Skill | Status this mode |
|-------|-------|------------------|
| spec (brainstorming) | `superpowers:brainstorming` | **skipped** ⏭️ — user authored the spec |
| grill | `grill-with-docs` | **pre-completed** ⏭️ — spec status line records a grill-with-docs pass (2026-06-17, 8 decisions, ADR-0021). Orchestrator must NOT auto-invoke. |
| plan | `superpowers:writing-plans` | **runs** (Opus) — ENTRY phase; reads the refined spec |
| impl | `superpowers:subagent-driven-development` | runs (Sonnet) |
| drift | in-prompt diff-vs-plan | runs (Sonnet) |
| ship | `/ship` | runs — opens PR + docs + inline review |
| post-ship verify | `/verify` (non-web XOR — never `/qa`) | runs (Sonnet) |
| pr-review | `/code-review` on the open PR | runs (Sonnet) |
| fix | triage subagent | runs only if a post-ship verdict FAILs |
| merge | `gh pr merge --squash --delete-branch` into `feat/b-set-live-spike` | runs after the 3 post-ship verdicts pass |

## Loop exit contract (item 001)

Merge requires all of: `items/001-drift.md` (PASS) · `items/001-ship.md` (PR URL) ·
`items/001-verify.md` (PASS) · `items/001-review.md` (PASS/PASS-WITH-NITS, inline from `/ship`) ·
`items/001-pr-review.md` (PASS/PASS-WITH-NITS). Grill verdict is absence-OK (spec mode ⏭️).

## Notes / constraints carried from the spec

- **No live anything in tests.** All drivers are injected; tests use fakes. The unit suite must
  not call live MSTR or a live provider. This is also the verify smoke boundary.
- **Follow CLAUDE.md (global FP rules):** pure functions where the spec marks a module `pure`;
  I/O at the edges (`runner`/`cli`); immutable records (frozen `BTrial`); TDD red-green-refactor.
- **Behavior-preserving refactor:** `multi_run.run_trials_k_valid` extraction must prove parity
  with the existing `run_task_k_valid` (spec §11.1, §8).
- **Integrity boundary** (spec §7): chat-loop allowlist-confined + new `file://` guard;
  `claude -p` residual limitation documented + store relocated (config/runbook, not enforced in code).
