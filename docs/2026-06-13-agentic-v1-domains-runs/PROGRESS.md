# PROGRESS — agentic_v1 domains + runs (continuation)

Legend: ⬜ todo · 🔄 in-progress · ✅ done · ⏭️ pre-completed/skipped · 🚧 partial (blocked sub-scope)

| # | id | spec | grill | plan | branch | impl | drift | ship | verify | pr-review | fix | merge |
|---|----|------|-------|------|--------|------|-------|------|--------|-----------|-----|-------|
| 008 | runner-harden | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#18] | ✅ | ✅ | ✅ r1 | ✅ [d6d5b9e] |
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
- 2026-06-13 — **008 drift ✅** (Sonnet, commit `c1eda30`): 0 findings, all 4 code-phase steps verified
  vs plan; ParseFailure.raw header-leak clear. **008 ship ✅** via **tier-2** (`gh pr create`, NOT /ship —
  repo uses plain gh squash PRs, no VERSION file, untracked 010 file in tree, flaky oracle suite; see
  items/008-ship.md). **PR #18** → main: https://github.com/snowshine0216/agent-eval-lab/pull/18.
  CHANGELOG `[Unreleased]` updated. Post-ship: dispatching review (tier-2 substitute) ‖ verify ‖ pr-review.
- 2026-06-13 — **008 post-ship round 1:** verify ✅ PASS (check-env + CLI integration tests + real local
  ollama smoke). review + pr-review BOTH independently caught a **latent blocker**: `_run_dset_command`
  lacked `except httpx.TransportError` (the live-roster path) → mid-corpus abort crashed uncaught + skipped
  the `.void.json` sidecar. Triage: 1 blocker (fix), 1 nit `history.py` shared mutable `_ELIDED_RESULT`
  (fix), 1 false-positive nit (skipped, verified). **Fix round 1** (Sonnet, commit `e297082`, pushed):
  added the TransportError guard (sidecar now written in both paths; clean exit-1) + regression test
  `test_run_dset_transport_error_gives_exit1_and_writes_void_sidecar` (red→green); fresh-dict `_elide`.
  Suite green (42 cli/history pass; only pre-existing oracle-subprocess flakes), ruff clean. Re-running
  review ‖ verify ‖ pr-review against `e297082`.
