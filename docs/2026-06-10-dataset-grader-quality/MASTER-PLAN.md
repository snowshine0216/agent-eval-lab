# MASTER-PLAN — Weeks 3-4: Dataset and Grader Quality

- **Mode:** backlog (full per-item pipeline: spec → grill → plan → branch →
  impl → drift → ship → (verify ‖ pr-review) → fix → merge)
- **Project type:** non-web (Python CLI) → post-ship XOR resolves to `/verify`
- **PR shape:** A (per-item PRs; no `--rollup` in the invocation)
- **Feature branch:** `autodev/dataset-grader-quality-feature` (synthesized off
  `main`; `main` is protected and the user did not opt into a protected merge
  this turn — feature branch is left open at close-out for user landing)
- **Branch prefix:** `claude/dataset-grader-quality-<id>`
- **Item order:** 001, 002, 003, 004 (locked after dependency scan — see
  PROGRESS.md note)
- **Sonnet override:** none (N=4, below the N≥5 cost-warning threshold;
  spec/grill/plan ride Opus per the model contract)

## Model contract

| Phase | Model |
|-------|-------|
| spec / grill / plan subagents | opus |
| impl / drift / verify / pr-review / fix subagents | sonnet |
| orchestrator | session default |

## Verification commands (used by impl, verify, ship)

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
```

Live-run validation (item 004) additionally sources keys from
`/Users/snow/Documents/Repository/.env` (`set -a; . ../.env; set +a`) and uses
the local MLX server at `localhost:11434` (already serving `Qwen/Qwen3-8B`).

## Workflow rules

- TDD per repo CLAUDE.md: failing test first, minimal green, refactor.
- Functional core / imperative shell: graders, metrics, parsing stay pure;
  provider calls and file I/O at edges.
- Frozen dataclasses (`kw_only=True`), tagged unions with `type`
  discriminators, no nullable maybe-fields (design doc §4.3).
- Every merge requires: drift PASS + ship artifact + grill PASS + verify
  PASS + review PASS/PASS-WITH-NITS + pr-review PASS/PASS-WITH-NITS.
- Reports land in `reports/` (gitignored) — surfaced to the user at
  close-out, not committed.
