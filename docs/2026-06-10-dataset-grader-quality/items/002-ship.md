PR: https://github.com/snowshine0216/agent-eval-lab/pull/6
Mode: A
Branch: claude/dataset-grader-quality-002
Base: autodev/dataset-grader-quality-feature
Title: feat(datasets): workspace-world v2 + taxonomy + rubric + 50 reviewed hard tasks (002)

Ship workflow: /ship 16-step. Pre-flight 11 commits / 14 files / +1345;
base already up to date; tests 225 → 227 after review-round fixes; ruff clean;
coverage = TDD + conformance suite; plan completion via drift PASS (after one
FAIL→fix round: knob restoration + proxy refinement); step-8 parallel review +
step-9 adversarial (1 P0 wrong-grade task + 3 conformance weaknesses → all
fixed pre-push, no-op guarantee added); no version bump ([Unreleased]
convention); CHANGELOG updated; push; PR #6.
