PR: https://github.com/snowshine0216/agent-eval-lab/pull/29
Mode: A
Branch: claude/harness-rounds-f-ablation-004
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.4 feat(datasets): F candidate-tree enrichment + overlay-disjointness (004)

## Ship summary
- /ship driven by orchestrator. Base = feature branch (main protected, no opt-in).
- Step 3 merge base: already up to date.
- Step 5 tests: **1046 passed / 18 skipped**, exit 0.
- Steps 8+9 review: **0 P0**. 2 P1 cleanups fixed pre-push (dead None-guard → direct read; dead test
  no-op). 2 accepted-by-design (F2 source-readable contract is intended enrichment; §10.4 invariant
  test repo-gated by macOS-local design, logic CI-enforced via the non-gated predicate unit test).
  → items/004-review.md **PASS-WITH-NITS**.
- Step 10 version bump: 0.2.3 → 0.2.4 (PATCH; pyproject.toml + uv.lock synced).
- Step 11 CHANGELOG: v0.2.4 entry.
- Staging discipline: only own files staged per commit; `git status` checked before each commit.
- PR #29 opened against the feature branch.
