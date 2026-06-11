# MASTER-PLAN — Weeks 5-6: Coding Agent Evaluation

Mode: **backlog** — full per-item pipeline (spec → grill → plan → branch → impl → drift → ship → (verify ‖ pr-review) → fix → merge), no phase skips.
Project type: **non-web** — Python CLI/library harness; post-ship verifier is `/verify` (never `/qa`).
PR shape: **A** (per-item PRs; no `--rollup` in the user's invocation).
Sonnet override: none (N=4 < 5; spec/grill/plan author on Fable per the model contract).
Item order: 001, 002, 003, 004 (pending dependency-scan confirmation — see below)

## Branch strategy

- Feature branch: `autodev/coding-agent-eval-feature` (synthesized off `main`, pushed 2026-06-11). All sub-PRs base here. **Never merged to `main` by autodev** — left open for user landing at close-out.
- Sub-branches: `claude/coding-agent-eval-<id>` per item, PR'd into the feature branch, squash-merged on gate pass.

## Model contract

| Phase | Model |
|-------|-------|
| spec / grill / plan subagents | fable |
| impl / drift / verify / pr-review / fix / dependency-scan / doc-sync subagents | sonnet |
| Orchestrator | session default (no override) |

## Workflow rules

- Per-phase task graph wired with `blockedBy` edges before each item starts; cross-item serialization via `<id>-merge` → `<next-id>-branch` edges.
- Every ✅ in PROGRESS.md carries mechanical evidence (file path, SHA, PR URL) per decompose.md.
- Per-item exit: drift + ship + grill PASS, and all three post-ship verdicts (verify, review, pr-review) PASS / PASS-WITH-NITS. No retry budget; environmental stops only.
- Run-level exit: run-doc-sync PASS + run-final-verify PASS + close-out presenting the **final evaluation report** (user-stated exit gate).
- Verification commands for the run: `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`.
