PR: https://github.com/snowshine0216/agent-eval-lab/pull/34
Mode: A
Branch: claude/m1-report-enhancement-001
Base: claude/fervent-panini-498c1a
Title: v0.3.0 feat(reports): M1 overview rollup + per-domain subreports (001)

Ship tool: /ship (16-step workflow, orchestrator-driven)
- Step 0-3: base = feature branch claude/fervent-panini-498c1a (non-protected); merge base "Already up to date".
- Step 5 tests: `uv run pytest` — 1131 passed / 26 skipped / 3 pre-existing failures (sandbox golden, evaluator.toml, B-store — fail on base branch too; missing local data, unrelated).
- Step 7 plan completion: all 10 plan tasks DONE (drift-confirmed).
- Step 8-9 review: see items/001-review.md (P0 admin-leak + never-raises hardening fixed pre-push).
- Step 10 version: MINOR bump 0.2.6 → 0.3.0 (new feature). Step 11 CHANGELOG updated. Step 12 no TODOS file.
- Step 13-15: committed, pushed, PR #34 opened.
