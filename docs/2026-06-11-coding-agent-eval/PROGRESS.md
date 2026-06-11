# PROGRESS — Weeks 5-6: Coding Agent Evaluation

Legend: ⏳ pending · 🔄 in progress · ✅ done (evidence below table) · ⚠️ soft fail (fix loop) · ⏭️ skipped by mode · ⛔ refused gate

| id | item | spec | grill | plan | branch | impl | drift | PR | QA | verify | review | pr-review | fix | merge |
|----|------|------|-------|------|--------|------|-------|----|----|--------|--------|-----------|-----|-------|
| 001 | code-world environment (isolated, reproducible) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-001 | ✅ 5dab58a | ✅ | ✅ #10 | ⏭️ | ✅ | ✅ | ✅ | ✅ 3 rounds (pre-PR) | ✅ eb8915b |

Evidence (001): grill items/001-grill.md (PASS) · drift items/001-drift.md (PASS) · PR https://github.com/snowshine0216/agent-eval-lab/pull/10 MERGED (items/001-ship.md) · verify items/001-verify.md (PASS — live entry-point smoke: broken→fixed tree, byte-identical reruns, timeout, env hermeticity) · review items/001-review.md (PASS-WITH-NITS, /ship steps 8+9 + adversarial ×4 rounds, fixes aeb124e/d9b1813/3b4b098/3489252) · pr-review items/001-pr-review.md (PASS-WITH-NITS, 2 nits, comment 4679039502) · fix: 3 rounds all pre-PR during ship; 0 post-PR rounds needed · merge eb8915b (squash, branch deleted)
| 002 | execution-based grader (tests as oracle) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-002 | ✅ 8fda0a5 | ✅ | ✅ #11 | ⏭️ | ✅ | ✅ | ✅ | ✅ 3 rounds (pre-PR) | ✅ 56a82b9 |

Evidence (002): grill items/002-grill.md (PASS) · drift items/002-drift.md (PASS 64/64, amendment 3cfdfe1) · PR https://github.com/snowshine0216/agent-eval-lab/pull/11 MERGED (items/002-ship.md) · verify items/002-verify.md (PASS — 19/19 live pipeline checks incl. reward-hack neutralization) · review items/002-review.md (PASS-WITH-NITS; 3 fix rounds: conftest --noconftest 93e4514, sitecustomize reservation 4f24a60, -c .harness.ini 54d9e9a, + 735a525/18b86a3/695f1f7/de071fd; adversarial round 4 CLEAN) · pr-review items/002-pr-review.md (PASS-WITH-NITS, 2 nits, comment 4679870319) · merge 56a82b9 (squash, branch deleted)
| 003 | code-repair dataset (10-20 tasks) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-003 | ✅ b01e34c | 🔄 | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |
| 004 | failure classification + final eval report | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ | ⏭️ | ⏳ | ⏳ | ⏳ | ⏳ | ⏳ |

Run-level: doc-sync ⏳ · final-verify ⏳ · close-out ⏳

Notes:
- QA column is ⏭️ for all items — project type is non-web; `/verify` is the post-ship verifier (XOR rule).
- Feature branch `autodev/coding-agent-eval-feature` synthesized off `main` and pushed 2026-06-11 (no user-named branch; protected-branch rule).
