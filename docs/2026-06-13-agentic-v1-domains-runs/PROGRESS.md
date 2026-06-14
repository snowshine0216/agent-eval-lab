# PROGRESS — agentic_v1 domains + runs (continuation)

Legend: ⬜ todo · 🔄 in-progress · ✅ done · ⏭️ pre-completed/skipped · 🚧 partial (blocked sub-scope)

| # | id | spec | grill | plan | branch | impl | drift | ship | verify | pr-review | fix | merge |
|---|----|------|-------|------|--------|------|-------|------|--------|-----------|-----|-------|
| 008 | runner-harden | ⏭️ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#18] | ✅ | ✅ | ✅ r1 | ✅ [d6d5b9e] |
| 009 | f-domain-adapter | ✅ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#19] | ✅ | ✅ | ✅ r1 | ✅ [331bbe8] |
| 010 | b-domain-m2 | ✅ | ⏭️ | ✅ | ✅ | ✅ | ✅ | ✅ [PR#21] | ✅ | ✅ | ✅ r1 | ✅ [4e57bc4] |

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
- 2026-06-14 — **009 MERGED** (PR #19, `331bbe8`): post-ship review+pr-review caught a residual golden
  leak in `test_f_run.py` + an F2 oracle false-negative (`extractDiagBlock` anchor); fixed
  `d9a7f9f`/`b94d24c`/`e5f7ad3` (anchor now var-name-agnostic; complete-token git-grep clean).
  condition_id="(f-local)" stub deferred → `items/009-plan.md §Execute-phase follow-ups`.
- 2026-06-14 — **Decision: build 010 code, DEFER all live runs.** D run stopped + state preserved;
  exact resume commands in **`EXECUTE-DEFERRED.md`**. 010 (B-domain/M2) branch cut + task graph set;
  spec/plan/impl NOT started. Owner artifacts: candidate MSTR acct + stripped strategy-test fork + B-1
  task + B-1 golden id STAGED; **B-2..B-10 + goldens STILL NEEDED** → M2 is a 1-task contingency.
- 2026-06-14 — **CI fixed** (PR #20, `4b143c2`): CI's `ruff format --check .` (whole repo) was red on
  main after #19 — `test_f2_oracle.py` left unformatted by the e5f7ad3 fix (dev only checked
  `--check src tests`). main green again. **Session paused for handoff → `HANDOFF-010.md`.**
- 2026-06-14 — **010 RESUMED** (fresh autodev session from `HANDOFF-010.md`). **Protected-base
  merge opt-in re-confirmed THIS turn** ("Squash-merge to main") — the handoff's prior-turn opt-in
  doesn't satisfy the protected-branch rule, so it was re-asked and GRANTED. Per-phase task graph
  recreated (010-{spec,grill,plan,branch,impl,drift,ship,verify,pr-review,fix,merge}). spec/grill
  ⏭️ pre-completed; branch already cut. **010-spec ✅** — `items/010-spec.md` authored from §4.3/
  §6/§7/§18.7–18.9 + D19/D20/D25/D26/D27/D33/D37 + the staged artifacts. CODE ONLY; live MSTR runs
  DEFERRED. Confirmed code facts: `Trajectory.run_uid` exists (D20 primitive); `_load_m1_domain_tasks`
  returns {D,F} (needs B); `reports/m1._DOMAINS=("F","D","B")` (B renders generically);
  `load_evaluator_config` ignores the B extras (010 parses `[candidate]`/`project_id`/`[oracle.b_set.goldens]`).
  Next: Opus plan subagent → `items/010-plan.md`.
- 2026-06-14 — **010 plan ✅** (Opus, `9eb74b2`): 10-task TDD plan mirroring F-domain; new `ReadbackSpec`
  variant + injectable `MstrReadbackClient` Protocol; golden/mutant fixtures gitignored-only;
  `requires_store` skipif; execute-phase follow-ups carved out for the deferred live run.
- 2026-06-14 — **010 impl ✅** (Sonnet subagent-driven, 10 commits `49eaae2`…`eb949ea`): config plumbing
  (`CandidateConfig`+`project_id`/`goldens`), `runners/mstr_client.py` (injectable Protocol),
  `runners/b_isolation.py` (D20 save-name/preflight/capture/reset), `datasets/skill_loader.py`,
  `datasets/b1_oracle.py` (`ReadbackSpec`+pure golden-discriminating grader), `datasets/b_tasks.py`
  (B-1 noskill/skill arms), `runners/b_run.py`, `m1_run` B branch, `cli` B wiring. **Orchestrator
  verified directly:** 940 passed/0 failed/0 skipped (local; `requires_store`/`requires_node` SKIP in
  CI), ruff check + `format --check .` clean (whole repo), **TRAP-1 leak grep CLEAN** — all real 010
  secrets (golden object id, project id, golden grid, MSTR host, store/skill paths) = 0 tracked-tree
  matches; flagged items are false positives (`playwright-cli` tool name; `mstr1` generic default in
  docs only; 6-char default pw coincidentally substring of the hex alphabet in 2 pre-existing untouched
  test files). Fixtures gitignored+unstaged. 2 minor deviations (CandidateConfig.url optional to match
  real config; 3 dependent fixtures updated). Next: drift subagent.
- 2026-06-14 — **010 drift ✅** (Sonnet, `f21e718`; plan amend `bccd719`): 10/10 plan tasks present in
  diff, 0 findings; both deviations ACCEPTED (CandidateConfig.url optional — plan amended; 3 dependent
  fixtures = necessary Task-1 consequence). Integrity spot-check clean (TRAP-2 prompt OK, grader
  pure/total, requires_store on all 3 oracle tests). **010 ship ✅ TIER-2** (`gh pr create`):
  **PR #21** → main: https://github.com/snowshine0216/agent-eval-lab/pull/21. CHANGELOG `[Unreleased]`
  updated. Pre-ship orchestrator leak-grep CLEAN. Post-ship: dispatching review (tier-2 substitute)
  ‖ verify ‖ pr-review.
- 2026-06-14 — **010 post-ship round 1:** verify ✅ PASS (oracle discriminates: golden PASS, 4 mutants +
  missing FAIL; M2 arms differ only by the stripped-skill injection; 940 passed). tier-2 review ✅
  PASS-WITH-NITS. **pr-review (`/code-review`) ✅ FAIL** — caught **2 real latent bugs** (both verified by
  the orchestrator against the code): (F1) `b_run.py` hardcoded `run_uid=__0000` → both M2 arms share a
  save-name, so D20 isolation depended on reset timing; (F2) `b1_oracle.py` strict order-sensitive grid
  equality → a correct candidate with reordered readback rows would false-FAIL (009-class oracle
  false-negative). Plus 2 nits (cli silent B-skip; hardcoded test path). **Fix round 1** (Sonnet,
  `be015a8`/`2c3fb13`/`8a3696c`/`dc33612`, pushed): F1 → per-task save-name `f"{condition_id}__{task_index:04d}"`
  via `enumerate` (distinct per arm); F2 → `_grid_matches` (header positional, data rows order-insensitive)
  **with discrimination preserved** (new tests: reordered-correct ⇒ PASS, wrong-value-reordered ⇒ FAIL);
  F3 nit → stderr diagnostic when B loaded but live client absent; F4 nit accepted (matches F-oracle path).
  **Re-ran all 3 verifiers vs `dc33612`:** review ✅ PASS, verify ✅ PASS, pr-review ✅ PASS (0 findings,
  both latent bugs resolved). 945 passed/0 failed, ruff clean. Leak re-grep CLEAN (golden id/project/host/
  grid = 0 tracked matches). **Loop exit contract satisfied** (all 3 PASS, 1 fix round). Next: pre-merge gate.
- 2026-06-14 — **010 MERGED to main** (PR #21, squash `4e57bc4`) — all pre-merge gates green
  (protected-base opt-in granted this turn; ship+drift+verify+review+pr-review all PASS; **PR CI green**
  — both `test` checks pass, `requires_store`/`requires_node` skip in CI as designed). Branch deleted.
  **Package 010 (B-domain/M2) CODE COMPLETE.** Like 008/009, the review+pr-review gates earned their
  keep: caught 2 real latent bugs (D20 save-name collision + an order-sensitive oracle false-negative),
  both fixed in 1 round. **All live MSTR/M2 runs remain DEFERRED to the owner** (`EXECUTE-DEFERRED.md`);
  B-2..B-10 + their goldens still NEEDED → M2 over B-1 is a 1-task contingency.
