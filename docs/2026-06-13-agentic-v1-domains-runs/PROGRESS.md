# PROGRESS — agentic_v1 domains + runs (continuation)

Legend: ⬜ todo · 🔄 in-progress · ✅ done · ⏭️ pre-completed/skipped · 🚧 partial (blocked sub-scope)

| # | id | spec | grill | plan | branch | impl | drift | ship | verify | pr-review | fix | merge |
|---|----|------|-------|------|--------|------|-------|------|--------|-----------|-----|-------|
| 008 | runner-harden | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | 🔄 | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 009 | f-domain-adapter | ⏭️ | ⏭️ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |
| 010 | b-domain-m2 | ⏭️ | ⏭️ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ | ⬜ |

`spec`/`grill` are ⏭️ for all items: the source spec is the brainstorm+grill output (§15/§15a/§15b/§18).

## Log
- 2026-06-13 — Run opened. Mode=backlog, **PR shape A (per-package PR → squash-merge to main; explicit opt-in)**,
  project=non-web→Verify. Scope decisions: **full roster** live runs authorized; **006 owner artifacts to be
  provided** by owner this session. Baseline: suite green, ruff clean, integrity gitignore guards verified.
- 2026-06-13 — **Impl mechanism corrected after user pushback:** 009/010 use
  `superpowers:subagent-driven-development` (Sonnet); 008 was inline-Opus and is KEPT.
- 2026-06-13 — **008 code written inline + TDD** (history-trim, provider-HTTP-error→recorded,
  incremental JSONL + void sidecar, local-Qwen id + siliconflow ladder). **Suite currently RED
  mid-edit** (test_cli slug/contract fixes remaining — see HANDOFF §3). **Session paused for handoff.**
  Resume doc: `/tmp/agentic-v1-domains-runs-HANDOFF.md`. Branch `feat/agentic-v1-008-runner-harden`,
  008 impl UNCOMMITTED (the diff is the impl). Next: finish §3 fixes → green → gates → PR → execute live k=5.
- 2026-06-13 — **Resumed; subagent-driven for all remaining work (user instruction).** Orchestrator
  coordinates (task graph, PROGRESS, git/PR ops); Sonnet subagents do impl/drift/verify/pr-review/fix.
  **008 impl ✅** — §3 test fixes confirmed, full suite green on clean run (889 passed/8 skipped;
  9 oracle-subprocess timeout flakes proven PRE-EXISTING by reproducing on base sans-008-diff),
  ruff clean. Commit `3ebd7d0`. ParseFailure.raw verified to carry response body only (no auth header).
  Next: drift subagent → ship → verify ‖ pr-review → fix → squash-merge to main → execute live k=5.
