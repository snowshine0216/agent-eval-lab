PR: https://github.com/snowshine0216/agent-eval-lab/pull/30
Mode: A
Branch: claude/harness-rounds-f-ablation-005
Base: autodev/harness-rounds-f-ablation-feature
Title: v0.2.5 feat(runners): Factor V confined-execution sandbox (005)

## Ship summary
- /ship driven by orchestrator. Base = feature branch (main protected, no opt-in).
- Step 3 merge base: already up to date.
- Step 5 tests: **1074 passed / 18 skipped**, exit 0.
- Steps 8+9 review: **security-focused** (code-reviewer + silent-failure-hunter + adversarial 15-vector
  test). **No P0 sandbox escape** — all golden-read + network-exfil vectors BLOCKED; no
  silently-unsandboxed path. 2 confirmed leaks/holes (unscoped file-read-metadata size-oracle;
  NODE_BIN allowlist injection) + 2 robustness fixed pre-push (`69300da`). Re-verified independently:
  stat(golden)+read(golden)+network all EPERM, node starts, 3 integration tests pass. →
  items/005-review.md **PASS-WITH-NITS**. Triage: items/005-ship-blocked.md.
- Step 10 version bump: 0.2.4 → 0.2.5 (PATCH; pyproject.toml + uv.lock synced).
- Step 11 CHANGELOG: v0.2.5 entry. Oracle (node_edge.py, execution.py) byte-identical.
- **Branch hygiene:** an unrelated user draft (m1-report-enhancement design, commit ec1cbe7) was
  rebased out of this branch pre-ship (preserved untracked on disk); an uncommitted user CONTEXT.md
  glossary change ("out-of-scope edit", same parallel work) was kept OUT of this PR and backed up to
  /tmp/context-out-of-scope-edit-glossary.diff. Staging was explicit-files-only throughout.
- PR #30 opened against the feature branch.
