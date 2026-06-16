PR: https://github.com/snowshine0216/agent-eval-lab/pull/31
Mode: A
Branch: claude/harness-rounds-f-ablation-006
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.6 feat(experiments): run-f-ablation driver + frozen f_ablation_spec (006)

## Ship summary
- /ship driven by orchestrator. Base = feature branch (main protected, no opt-in).
- Step 3 merge base: already up to date.
- Step 5 tests: **1095 passed / 18 skipped**, exit 0.
- Steps 8+9 review: **no accidental paid execution** (3 reviewers + CLEAN adversarial). A latent defect
  (driver buffered all 240 paid results → mid-run error lost everything) + non-atomic sidecar + a
  misleading `correction="holm"` on the descriptive spec, all fixed pre-push (`2728c95`): crash-safe
  streaming driver, atomic sidecar, honest `correction="none"`. M1 frozen hash UNCHANGED. →
  items/006-review.md **PASS-WITH-NITS**. Triage: items/006-ship-blocked.md.
- Step 10 version bump: 0.2.5 → 0.2.6 (PATCH; pyproject.toml + uv.lock synced).
- Step 11 CHANGELOG: v0.2.6 entry.
- **Worktree hygiene:** the user is editing in parallel in this worktree (reports/validation.py,
  test_validation.py — self-consistent, 18 tests pass); those files were never staged. Staging was
  explicit-files-only throughout.
- PR #31 opened against the feature branch.
