PR: https://github.com/snowshine0216/agent-eval-lab/pull/28
Mode: A
Branch: claude/harness-rounds-f-ablation-003
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.3 feat(datasets): F ablation arm-as-task + Factor P (003)

## Ship summary
- /ship driven by orchestrator. Base overridden to the feature branch (not main — protected, no opt-in).
- Step 3 merge base: already up to date.
- Step 5 tests: **1033 passed / 18 skipped**, exit 0.
- Steps 8+9 review: initial **FAIL** — 1 latent P0 (`build_candidate_tree` F3 dispatch missed armed
  ids) + CI-red `ruff check` on the new test files (and 2 pre-existing E501s on the feature base).
  Routed through a pre-push fix round (commit `8900c1f`) → re-verified clean → items/003-review.md
  **PASS-WITH-NITS**. Details in items/003-ship-blocked.md.
- Step 10 version bump: 0.2.2 → 0.2.3 (PATCH; pyproject.toml + uv.lock synced).
- Step 11 CHANGELOG: v0.2.3 entry (Added/Changed/Fixed).
- Step 12 TODOS: none (no TODOS.md).
- Staging discipline: only own files staged per commit (no broad `git add`); `git status` checked
  before each commit (security lesson from item 002).
- PR #28 opened against the feature branch.
