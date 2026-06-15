PR: https://github.com/snowshine0216/agent-eval-lab/pull/27
Mode: A
Branch: claude/harness-rounds-f-ablation-002
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.2 feat(runners): per-domain max_rounds turn-bound + recorded policy fields (002)

## Ship summary
- /ship driven by orchestrator. Base overridden to the feature branch (not main).
- Step 5 tests: **1021 passed / 17 skipped**, exit 0 (post-fix).
- Steps 8+9 review: initial **FAIL** on 2 latent bugs (F1 dset_run safety_cap thread; F2 env_unhealthy
  override incl. max_rounds) → fixed pre-push in fix round 1 → focused re-review BOTH FIXED →
  items/002-review.md **PASS-WITH-NITS**.
- Step 10 version bump: 0.2.1 → 0.2.2 (PATCH).
- Step 11 CHANGELOG: v0.2.2 entry.
- **Security remediation:** the impl step's broad `git add` swept `.env.bak.1781491343` (an OpenRouter
  key) into commit 73c7cc0. GitHub push protection blocked the first push — **the key never reached
  GitHub**. Branch history rewritten via soft-reset to a single clean commit (7a5e822); `.env.bak*` and
  `*.bak` added to `.gitignore`. The local `.env.bak.*` file is left on disk, untracked. **User should
  rotate that OpenRouter key as a precaution.**
- PR #27 opened (one consolidated commit).
