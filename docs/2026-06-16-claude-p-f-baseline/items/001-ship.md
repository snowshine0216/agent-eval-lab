PR: https://github.com/snowshine0216/agent-eval-lab/pull/38
Mode: A
Branch: claude/claude-p-f-baseline-001
Base: feat/claude-p-f-baseline
Title: feat(claude-baseline): vanilla claude -p F-task baseline (001)

## Ship workflow notes
- Base OVERRIDDEN to the feature branch `feat/claude-p-f-baseline` (non-protected); never `main` (no opt-in).
- Step 5 (tests): full suite green (`uv run pytest -q` exit 0; 7 new tests added for pre-push fixes), ruff check + format clean.
- Steps 8+9 (review): 3 reviewers; 3 blockers fixed pre-push (commits 80bf605, 9b7d571); verdict captured inline → `items/001-review.md` (PASS-WITH-NITS).
- Step 10 (version): SKIPPED — sub-item PR into a feature branch; no VERSION file in repo; release bump deferred to the owner-driven feat→main landing. CHANGELOG entry added under `## Unreleased`.
- Step 12 (TODOS.md): none in repo — skipped.
