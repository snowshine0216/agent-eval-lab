PR: https://github.com/snowshine0216/agent-eval-lab/pull/2
Mode: A
Branch: claude/tool-use-slice-001
Base: claude/gracious-villani-753e22
Title: v0.2.0 feat(eval): Weeks 1-2 tool-use evaluation slice (001)

Ship tool: /ship (16-step workflow, run inline by the orchestrator).
- Steps 0–3: GitHub; base overridden to the feature branch (not main); merge-base already up to date.
- Step 5: 88 tests pass; ruff check + format clean.
- Step 7: plan completion — 24/24 (drift-verified).
- Steps 8+9: pre-landing parallel review + adversarial review → 2 real grader-taxonomy bugs fixed pre-PR (commits 56399c8, ab5d9c8); verdict captured in items/001-review.md (PASS-WITH-NITS).
- Step 10: version 0.1.0 → 0.2.0 (MINOR, feature slice; autonomous default in this unattended run).
- Step 11: CHANGELOG.md created with the v0.2.0 section.
- Step 12: no TODOS.md in repo — skipped.
- Steps 13–15: committed (7cdd465), pushed, PR #2 opened against the feature branch.
