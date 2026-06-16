# MASTER-PLAN — claude-p F baseline

**Mode:** plan
**Project type:** non-web   (Python eval-lab CLI/library — post-ship gate is `/verify`, never `/qa`)
**PR shape:** A   (per-item PR; no `--rollup` in the invocation)
**Feature branch:** `feat/claude-p-f-baseline`   (current branch; non-protected — sub-branch lands here, nothing touches `main`)
**Sub-branch:** `claude/claude-p-f-baseline-001`
**Item order:** 001 (single item — degenerate N=1)

## Per-mode skill skips (plan mode)

| Phase | Skill | Status |
|-------|-------|--------|
| spec | `superpowers:brainstorming` | ⏭️ skipped — user-provided plan |
| grill | `grill-with-docs` | ⏭️ skipped — user-authored input (orchestrator MUST NOT auto-invoke) |
| plan | `superpowers:writing-plans` | ⏭️ skipped — user-provided plan |
| impl | `superpowers:subagent-driven-development` | runs (ENTRY dispatch) |
| drift | in-prompt Sonnet logic | runs |
| ship | `/ship` (review captured inline) | runs |
| verify | `/verify` (non-web XOR) | runs — entry-point smoke = the no-quota `--dry-run` |
| pr-review | `/code-review` | runs |
| fix | Sonnet triage | runs if any post-ship verdict FAILs |
| merge | `gh pr merge --squash --delete-branch` into the feature branch | runs |

## Environment notes (load-bearing)

- **Node ≥20 for the oracle:** default PATH node is **v16.20.2 (incapable)**. A
  capable binary exists at `~/.nvm/versions/node/v22.22.2/bin/node`. Only the
  *paid* oracle-grading path needs it; unit tests stub the oracle, and the
  `--dry-run` verify smoke needs no Node. Per memory `f-oracle-node-20-requirement`.
- **`claude` CLI:** 2.1.177 at `/Users/snow/.local/bin/claude` (matches the plan).
- **No VERSION file** — repo tracks `CHANGELOG.md` only; `/ship` must not invent a
  VERSION bump (memory: squash-merge + CHANGELOG, no VERSION bump).
- **Billing:** session OAuth/subscription (quota, not per-token $); `total_cost_usd`
  is an informational efficiency metric only.

## Loop exit contract (plan mode, non-web)

Three post-ship verdicts must read `PASS` / `PASS-WITH-NITS`:
`items/001-verify.md` (XOR with qa) + `items/001-review.md` (inline from `/ship`)
+ `items/001-pr-review.md`. Plus `items/001-drift.md` and `items/001-ship.md`.
`items/001-grill.md` does NOT exist (pre-skipped). Environmental stops only — no
technical-"stuck" bail.

## Protected-branch guard

`main` is protected and the invocation contained **no** opt-in. The feature
branch `feat/claude-p-f-baseline` is left OPEN at Phase 3 as a roll-up review
surface (PR into `main`, not merged).
