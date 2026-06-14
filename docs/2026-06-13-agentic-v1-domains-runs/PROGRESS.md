# PROGRESS — agentic_v1 domains + runs (continuation)

Legend: ⬜ todo · 🔄 in-progress · ✅ done · ⏭️ pre-completed/skipped · 🚧 partial (blocked sub-scope)

| # | id | spec | grill | plan | branch | impl | drift | ship | verify | pr-review | fix | merge |
|---|----|------|-------|------|--------|------|-------|------|--------|-----------|-----|-------|
| 008 | runner-harden | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#18] | ✅ | ✅ | ✅ r1 | ✅ [d6d5b9e] |
| 009 | f-domain-adapter | ✅ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#19] | ✅ | ✅ | ✅ r1 | ✅ [331bbe8] |
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
- 2026-06-14 — **009 MERGED to main** (PR #19, squash `331bbe8`). Post-ship review+pr-review caught TWO
  more real issues (1 round to fix): a **residual integrity leak** (`test_f_run.py` embedded the golden
  string `const diagResult = await analyzeFailure` — missed by the earlier incomplete-token grep) and an
  **F2 oracle false-negative** (`extractDiagBlock` anchored on an unprompted comment, then on the exact
  var name → would false-FAIL correct candidates). Fixed `d9a7f9f`/`b94d24c`/`e5f7ad3`: leak removed
  (complete-token git-grep now clean), anchor made variable-name-agnostic with explicit fail-if-absent.
  condition_id="(f-local)" stub deferred to plan §"Execute-phase follow-ups" (needed before live F run).
- 2026-06-14 — **D run RELAUNCHED** after the site restart (user) with a progress-based stall watchdog
  (`/tmp/run-d-k5-v2.sh`, kills an arm only on 20m of no output-file growth — healthy arms run to
  completion). deepseek task 1 done ~21m (cold-start after restart); monitoring steady-state pace.
- 2026-06-14 — **010 (B-domain/M2) branch cut** `feat/agentic-v1-010-b-domain-m2`. Owner artifacts:
  candidate MSTR acct + stripped strategy-test fork + B-1 task + B-1 golden id all STAGED (see
  items/010-b-domain-artifacts.md); B-2..B-10 + their goldens STILL NEEDED → M2 is a 1-task contingency.
- 2026-06-14 — **008 MERGED to main** (PR #18, squash `d6d5b9e`) — all gates green, one real latent
  bug (run-dset TransportError gap) caught by review+pr-review and fixed in 1 round.
- 2026-06-14 — **008 EXECUTE started:** re-froze M1 spec for `local:Qwen/Qwen3-8B` (spec_hash
  `ca4467f2`; existing pilot runs were k=2 → not reusable for k=5). check-env green (MSTR 204, all 6
  arm keys present). **Launched D k=5 roster (6 arms) in background** (deepseek/glm/minimax/
  sf-397b/sf-35b/local; sequential; log `reports/agentic-v1/run-d-k5.log`). Per user: "run D now,
  code in parallel". **009 (F-domain) started in parallel** — branch `feat/agentic-v1-009-f-domain`
  off main, spec authored (items/009-spec.md), plan phase next (Fable subagent).
- 2026-06-14 — **009 spec ✅ + plan ✅** (plan via Opus — Fable unavailable in env; commit bbaa1f9).
  **009 impl** (Sonnet, 7 TDD tasks 5335e6c…2389e44): F1/F2 env-free node oracles
  (golden⇒PASS / prefix 5b0c13a6⇒FAIL / 2 named mutants each⇒FAIL), build_f_tasks, run-m1 F wiring;
  suite green (oracle flakes excepted), ruff clean. **⚠️ Pre-ship INTEGRITY BLOCKER caught by
  orchestrator before ship (NOT shipped):** (1) `f_tasks.py` candidate prompt leaks the golden-NEW
  helper `waitForSnapshotFinalNotificationByName` + solution mechanics (spec §4.1 withhold-localization
  + §7 "golden reachable from prompt"); (2) `tests/datasets/test_f1_oracle.py` (TRACKED/PUBLIC)
  hardcodes verbatim golden answer in mutant `.replace()` strings (D19/D33 — goldens must live only in
  gitignored evaluator-only/). Dispatching pre-ship fix: de-leak prompts to problem-level; move mutant
  fixtures into evaluator-only/; git-grep tracked tree clean of golden tokens; re-verify discriminating.
