# PROGRESS — Weeks 5-6: Coding Agent Evaluation

Legend: ⏳ pending · 🔄 in progress · ✅ done (evidence below table) · ⚠️ soft fail (fix loop) · ⏭️ skipped by mode · ⛔ refused gate

| id | item | spec | grill | plan | branch | impl | drift | PR | QA | verify | review | pr-review | fix | merge |
|----|------|------|-------|------|--------|------|-------|----|----|--------|--------|-----------|-----|-------|
| 001 | code-world environment (isolated, reproducible) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-001 | ✅ 5dab58a | ✅ | ✅ #10 | ⏭️ | ✅ | ✅ | ✅ | ✅ 3 rounds (pre-PR) | ✅ eb8915b |

Evidence (001): grill items/001-grill.md (PASS) · drift items/001-drift.md (PASS) · PR https://github.com/snowshine0216/agent-eval-lab/pull/10 MERGED (items/001-ship.md) · verify items/001-verify.md (PASS — live entry-point smoke: broken→fixed tree, byte-identical reruns, timeout, env hermeticity) · review items/001-review.md (PASS-WITH-NITS, /ship steps 8+9 + adversarial ×4 rounds, fixes aeb124e/d9b1813/3b4b098/3489252) · pr-review items/001-pr-review.md (PASS-WITH-NITS, 2 nits, comment 4679039502) · fix: 3 rounds all pre-PR during ship; 0 post-PR rounds needed · merge eb8915b (squash, branch deleted)
| 002 | execution-based grader (tests as oracle) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-002 | ✅ 8fda0a5 | ✅ | ✅ #11 | ⏭️ | ✅ | ✅ | ✅ | ✅ 3 rounds (pre-PR) | ✅ 56a82b9 |

Evidence (002): grill items/002-grill.md (PASS) · drift items/002-drift.md (PASS 64/64, amendment 3cfdfe1) · PR https://github.com/snowshine0216/agent-eval-lab/pull/11 MERGED (items/002-ship.md) · verify items/002-verify.md (PASS — 19/19 live pipeline checks incl. reward-hack neutralization) · review items/002-review.md (PASS-WITH-NITS; 3 fix rounds: conftest --noconftest 93e4514, sitecustomize reservation 4f24a60, -c .harness.ini 54d9e9a, + 735a525/18b86a3/695f1f7/de071fd; adversarial round 4 CLEAN) · pr-review items/002-pr-review.md (PASS-WITH-NITS, 2 nits, comment 4679870319) · merge 56a82b9 (squash, branch deleted)
| 003 | code-repair dataset (10-20 tasks) | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-003 | ✅ b01e34c | ✅ | ✅ #12 | ⏭️ | ✅ | ✅ | ✅ | ✅ 1 round (pre-PR) | ✅ 4e908f3 |

Evidence (003): grill items/003-grill.md (PASS) · drift items/003-drift.md (PASS 20/20 + sha gates) · PR https://github.com/snowshine0216/agent-eval-lab/pull/12 MERGED (items/003-ship.md) · verify items/003-verify.md (PASS — live loader/oracle pipeline on 3 tiers + conformance 32/32) · review items/003-review.md (PASS-WITH-NITS; oracle-breadth fix round 336805b/77fa3dd; hack-resistance re-verification CLEAN) · pr-review items/003-pr-review.md (PASS-WITH-NITS, 3 nits, comment 4680629754) · merge 4e908f3 (squash, branch deleted)
| 004 | failure classification + final eval report | ✅ | ✅ | ✅ | ✅ claude/coding-agent-eval-004 | ✅ e371db3 | ✅ | ✅ #13 | ⏭️ | 🔄 | ✅ | 🔄 | ✅ 1 round (pre-PR) | ⏳ |

Evidence (004): grill items/004-grill.md (PASS) · drift items/004-drift.md (PASS, sha gates + Part B mechanical) · PR https://github.com/snowshine0216/agent-eval-lab/pull/13 (items/004-ship.md) · review items/004-review.md (PASS-WITH-NITS; truncation harness-defect fix round a819ab4/3116c74/3236b3a/0cca10b; validity re-verification CLEAN)

Evidence (004, fix round 1 — harness defect from validity review): the client sent no max_tokens, so the MLX server's 512-token default truncated Qwen3-8B inside its reasoning channel on 30/45 local runs (27 with completion_tokens == 512 exactly), misclassified by fc-v1 as agent_failure/malformed_reply. Fix: explicit `--max-tokens` (default 4096) threaded client→loop→multi_run→CLI and recorded per trajectory + fc-v2 (`token_budget_exhausted`, parse_failure None-guard) — a819ab4 · rerun artifacts C4 45/45 passed (pass@1 0.133→1.000) + C3 minimax retry completed 45/45 (replaces 6-row partial) — 3116c74 · report regenerated under fc-v2 with defect narrative, fc design note (cr-007/cr-014), budget-asymmetry limitation, saturation takeaway; byte-identical re-regeneration (sha256 05139448…) — 3236b3a · CHANGELOG — 0cca10b · gates: 664 tests green (+17), ruff check/format clean.

Run-level: doc-sync ⏳ · final-verify ⏳ · close-out ⏳

Notes:
- QA column is ⏭️ for all items — project type is non-web; `/verify` is the post-ship verifier (XOR rule).
- Feature branch `autodev/coding-agent-eval-feature` synthesized off `main` and pushed 2026-06-11 (no user-named branch; protected-branch rule).
