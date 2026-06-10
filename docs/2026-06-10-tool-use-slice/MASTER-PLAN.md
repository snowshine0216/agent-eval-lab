# MASTER-PLAN — Weeks 1–2 Tool-Use Vertical Slice

- **Mode:** spec
- **Project type:** non-web   (post-ship verifier = `/verify`, never `/qa`)
- **PR shape:** A  (per-item PR; default — no `--rollup` in the invocation)
- **N items:** 1

## Branch strategy

- **Default branch:** `main` (protected — never auto-merged by this run).
- **Feature branch:** `claude/gracious-villani-753e22` (current, non-protected). Sub-PR lands here; Phase 3 opens a `claude/gracious-villani-753e22 → main` PR (opened, not merged) for the user to land.
- **Item 001 sub-branch:** `claude/tool-use-slice-001`, cut from the feature branch.

## Per-mode skill skips (spec mode)

| Phase | Skill | Status this run |
|-------|-------|-----------------|
| spec (brainstorming) | `superpowers:brainstorming` | **SKIPPED** ⏭️ — user authored the spec (design doc §16). |
| grill | `grill-with-docs` | **PRE-COMPLETED** ⏭️ — user-grilled; orchestrator MUST NOT auto-invoke. |
| plan | `superpowers:writing-plans` (Opus) | **RUNS** — entry dispatch; reads `items/001-spec.md`. |
| impl | `superpowers:subagent-driven-development` (Sonnet) | runs |
| drift | in-prompt Sonnet, no skill | runs |
| ship | `/ship` (primary), `gh pr create` (last resort) | runs |
| verify | `/verify` (non-web branch of XOR) | runs — **never `/qa`** |
| review | captured inline from `/ship` steps 8+9 | runs (no separate dispatch) |
| pr-review | `/code-review` on open PR | runs |
| fix | Sonnet triage | as needed (no retry budget) |
| merge | `gh pr merge --squash --delete-branch` into feature branch | runs after pre-merge gate |

## Model selection (subagent contract)

- Orchestrator (this session): session default — no override.
- Plan subagent: `model="opus"`.
- Impl / drift / verify / pr-review / fix subagents: `model="sonnet"`.

## Key environment facts (locked at intake)

- **No provider API keys in env.** The OpenAI-compatible provider client and the
  runner are therefore built **test-first against a fake/recorded transport**
  (VCR-style cassettes + a deterministic fake model), per design §12. **No live
  model calls in this run.** The client's public shape is real; only the
  transport is faked for tests.
- `uv` drives the toolchain (system Python is 3.9; `uv run` uses the project's
  3.11+ interpreter). Validation commands: `uv run pytest`,
  `uv run ruff check .`, `uv run ruff format --check .`.
- Functional-core / imperative-shell is a hard constraint (AGENTS.md, CLAUDE.md):
  pure core (tasks/tools/graders/metrics/reports models), effects only at edges
  (runner, dataset/report I/O). TDD red-green-refactor, files < 200 lines,
  functions < 20 lines where practical.

## Loop exit contract (spec mode)

Merge only when ALL of these exist with passing verdicts:
`items/001-drift.md` (PASS) · `items/001-ship.md` (`PR: …`) ·
`items/001-verify.md` (PASS) · `items/001-review.md` (PASS|PASS-WITH-NITS) ·
`items/001-pr-review.md` (PASS|PASS-WITH-NITS) · plus `001-spec.md` + `001-plan.md` present.
Grill verdict is absence-OK (⏭️ user-grilled).
