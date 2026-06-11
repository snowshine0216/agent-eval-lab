PR: https://github.com/snowshine0216/agent-eval-lab/pull/8
Mode: A
Branch: claude/dataset-grader-quality-004
Base: autodev/dataset-grader-quality-feature
Title: feat(validation): per-task step budgets, config comparison, live v2 reports (004)

Ship workflow: /ship 16-step. Pre-flight 11 commits / 21 files / +2101; base
up to date; tests 345 → 357 after review-round fixes; ruff clean; coverage =
TDD + hand-verified bootstrap vectors + independent adversarial recount of
every committed report number (all exact); plan completion via drift PASS
12/12 (incl. live-protocol verification: 5×150-line artifacts,
regeneration byte-determinism); step-8 parallel + step-9 adversarial review
(2 P0 latent + 5 P1 + verdict-honesty finding → all fixed pre-push; reports
regenerated with the honestly-downgraded discriminativeness verdict); no
version bump ([Unreleased] convention); CHANGELOG updated; push; PR #8.
Live-protocol note: Task 10 was executed by the orchestrator via background
jobs (the impl subagent's dispatch ended mid-protocol — session lifetime);
identical commands modulo the plan's console-script typo (amended in plan).
