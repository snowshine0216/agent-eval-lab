# PROGRESS — Weeks 5-6: Coding Agent Evaluation

Legend: ⏳ pending · 🔄 in progress · ✅ done (evidence below table) · ⚠️ soft fail (fix loop) · ⏭️ skipped by mode · ⛔ refused gate

| id | item | spec | grill | plan | branch | impl | drift | PR | QA | verify | review | pr-review | fix | merge |
|----|------|------|-------|------|--------|------|-------|----|----|--------|--------|-----------|-----|-------|
| 001 | code-world environment (isolated, reproducible) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-001 | ✅ 5dab58a | 🔄 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 002 | execution-based grader (tests as oracle) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 003 | code-repair dataset (10-20 tasks) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 004 | failure classification + final eval report | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

Run-level: doc-sync ⏳ · final-verify ⏳ · close-out ⏳

Notes:
- QA column is ⏭️ for all items — project type is non-web; `/verify` is the post-ship verifier (XOR rule).
- Feature branch `autodev/coding-agent-eval-feature` synthesized off `main` and pushed 2026-06-11 (no user-named branch; protected-branch rule).
