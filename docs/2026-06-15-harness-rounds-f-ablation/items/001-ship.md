PR: https://github.com/snowshine0216/agent-eval-lab/pull/26
Mode: A
Branch: claude/harness-rounds-f-ablation-001
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.1 feat(reports): fc-v4 classifier + pass^k censoring (001)

## Ship summary
- /ship driven by orchestrator (16-step workflow). Base overridden to the feature branch (not main).
- Step 5 tests: **993 passed / 17 skipped**, exit 0.
- Steps 8+9 review captured inline → items/001-review.md (Verdict: PASS-WITH-NITS; adversarial CLEAN).
- Step 10 version bump: 0.2.0 → 0.2.1 (PATCH; internal eval-pipeline change, pre-1.0).
- Step 11 CHANGELOG: v0.2.1 entry added.
- Steps 13–15: committed, pushed, PR #26 opened.
- Stray untracked files (`learning/`, `.env.bak.*`) deliberately excluded from the commit.
