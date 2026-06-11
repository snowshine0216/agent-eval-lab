# PROGRESS — Weeks 5-6: Coding Agent Evaluation

Legend: ⏳ pending · 🔄 in progress · ✅ done (evidence below table) · ⚠️ soft fail (fix loop) · ⏭️ skipped by mode · ⛔ refused gate

| id | item | spec | grill | plan | branch | impl | drift | PR | QA | verify | review | pr-review | fix | merge |
|----|------|------|-------|------|--------|------|-------|----|----|--------|--------|-----------|-----|-------|
| 001 | code-world environment (isolated, reproducible) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-001 | ✅ 5dab58a | ✅ | ✅ #10 | ⏭️ | 🔄 | ✅ | 🔄 | ⏳ | ⏳ |

Evidence (001): grill items/001-grill.md (PASS) · drift items/001-drift.md (PASS) · PR https://github.com/snowshine0216/agent-eval-lab/pull/10 (items/001-ship.md) · review items/001-review.md (PASS-WITH-NITS, /ship steps 8+9 + adversarial ×4 rounds, fixes aeb124e/d9b1813/3b4b098/3489252)
| 002 | execution-based grader (tests as oracle) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 003 | code-repair dataset (10-20 tasks) | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 004 | failure classification + final eval report | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

Run-level: doc-sync ⏳ · final-verify ⏳ · close-out ⏳

Notes:
- QA column is ⏭️ for all items — project type is non-web; `/verify` is the post-ship verifier (XOR rule).
- Feature branch `autodev/coding-agent-eval-feature` synthesized off `main` and pushed 2026-06-11 (no user-named branch; protected-branch rule).
