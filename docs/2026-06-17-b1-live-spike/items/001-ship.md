PR: https://github.com/snowshine0216/agent-eval-lab/pull/44
Mode: A
Branch: claude/b1-live-spike-001
Base: feat/b-set-live-spike
Title: v0.6.0 feat(b1-spike): B-1 live spike — run-b/report-b human-scored eval (001)

## /ship summary

- 16-step `/ship` workflow run via the autodev orchestrator (base overridden to the feature branch, not main).
- Base merge: already up to date. Full suite: 1251 passed, 18 skipped. Ruff clean.
- Version bump: v0.5.1 → **v0.6.0** (MINOR — new `run-b`/`report-b` feature; lockfile synced version-only).
- CHANGELOG: v0.6.0 section added (Added: run-b/report-b + modules + console entry; Changed: run_trials_k_valid extraction, file:// guard, candidate folder + fail-fast).
- Steps 8+9 review: 2 P0 + 4 P1 surfaced and **fixed pre-PR** (commits 74a5870, a4818e6); re-review CONFIRMED-CLEAN → review verdict PASS ([items/001-review.md](001-review.md)).
- TODOS.md: none (step 12 skipped).
