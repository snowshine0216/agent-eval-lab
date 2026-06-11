PR: https://github.com/snowshine0216/agent-eval-lab/pull/7
Mode: A
Branch: claude/dataset-grader-quality-003
Base: autodev/dataset-grader-quality-feature
Title: feat(graders): LLM-judge grader + κ calibration harness with provisional run (003)

Ship workflow: /ship 16-step. Pre-flight 16 commits / 31 files / +2343; base
up to date; tests 296 → 315 after review-round fixes; ruff clean (orchestrator
fixed 6 lint errors left by impl before drift); coverage = TDD 1:1 + κ
literature vectors; plan completion via drift PASS 23/23; step-8 parallel +
step-9 adversarial review (2 P0 + 4 P1 + fixture-difficulty finding → all
fixed pre-push incl. 4 boundary fixtures + provisional re-run, κ 0.8621→0.8725
n=19); no version bump ([Unreleased] convention); CHANGELOG updated; push;
PR #7. Note: gh keyring auth flaked mid-ship (API 401 with valid token) —
worked around with explicit GH_TOKEN from `gh auth token`.
