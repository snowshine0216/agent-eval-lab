# Handoff — agentic_v1 Package 010 (B-domain/M2) + deferred live runs

**For:** a fresh autodev session. **Date:** 2026-06-14. **Repo:** `~/Documents/Repository/agent-eval-lab` (PUBLIC).
**You MUST use the `autodev` skill** (`.autodev-current` → `docs/2026-06-13-agentic-v1-domains-runs/`).

---

> ## ✅ 010 COMPLETE — this handoff is DONE (2026-06-14)
> Package 010 (B-domain/M2) CODE was built through the full autodev loop and **squash-merged to `main`
> (PR #21, `4e57bc4`)**. All three packages (008/009/010) are now merged; the run's **CODE phase is
> complete**. The review→fix loop caught 2 real latent bugs (a D20 save-name collision between the M2
> arms + an order-sensitive oracle false-negative), both fixed in 1 round. `PROGRESS.md` shows the full
> ✅ matrix.
>
> **A fresh session should NOT redo 010.** The only remaining work is the owner's **DEFERRED live
> execute** → go to **`EXECUTE-DEFERRED.md`** (now has concrete B/M2 steps in §3). The rest of this
> file is retained as the build-time record.

---

## 0. TL;DR — what's done, what's next
- **008 (runner-harden) ✅ MERGED** to main (PR #18, `d6d5b9e`). **009 (F-domain F1/F2) ✅ MERGED** (PR #19, `331bbe8`). **CI green** (ruff hotfix PR #20, `4b143c2`).
- **010 (B-domain/M2): NOT STARTED** beyond branch + task-graph + tracker. **Build its CODE** through the full autodev loop, tier-2 PR → squash-merge to `main`. **Live MSTR runs are DEFERRED** (code only).
- **All live execute (D / F / B-M2 runs + the final M1 report) is DEFERRED to the owner** — exact commands in **`EXECUTE-DEFERRED.md`**. Do NOT launch live runs unless the user asks.
- Source of truth: read `PROGRESS.md`, `MASTER-PLAN.md`, `MASTER-SPEC.md`, `items/010-b-domain-artifacts.md`, and source spec `docs/superpowers/specs/2026-06-12-use-case-agentic-eval-design.md` (§4.3, §18.7–18.9).

## 1. Operating contract (decisions already made — do NOT relitigate)
- **autodev backlog mode**; per-item spec+grill are **PRE-COMPLETED ⏭️** (the source spec is the grill output).
- **Subagent-driven for ALL work** (user instruction): orchestrator coordinates (task graph, PROGRESS, git/PR ops); **Sonnet** subagents do impl/drift/verify/pr-review/fix. **Spec/plan authoring → `model="opus"`** because **Fable is NOT available in this environment** (`claude-fable-5` errors) — Opus is the reserved fallback for judgment-heavy plan authoring.
- **PR shape A — per-package PR → squash-merge to `main`** (protected-base opt-in GRANTED: *"each as its own PR to main (squash)"*).
- **Ship is TIER-2** (`gh pr create`, NOT `/ship`): repo convention is plain gh squash PRs, no VERSION file, the suite has flaky oracle-subprocess tests. Tier-2 contract = dispatch a Sonnet **review** subagent (`items/<id>-review.md`) + `/code-review` **pr-review** subagent. Both gate merge. See `items/008-ship.md`/`009-ship.md` for the exact pattern.
- **Project = non-web → Verify** (not QA). 010's verify is DETERMINISTIC (stubbed MSTR) — the live readback is deferred.
- **gh API 401s intermittently** on this network → prefix `GH_TOKEN="$(gh auth token)"` + a retry loop (memory `gh-api-auth-flake-workaround`).
- **CI** (`.github/workflows/ci.yml`) runs `uv run pytest` → `ruff check .` → **`ruff format --check .` (WHOLE repo)**. ⚠️ Always run `uv run ruff format --check .` (not just `src tests`) before pushing — that gap caused the #20 hotfix.

## 2. Package 010 — what to build (CODE only; live runs deferred)
Spec §4.3/§18.7/§18.8/§18.9; decisions D19/D20/D25/D26/D27/D37. **Owner artifacts are STAGED** (see `items/010-b-domain-artifacts.md`): candidate MSTR account (`evaluator.toml [candidate]`, least-priv, ≠ evaluator `mstr1`, can't read golden), the stripped knowledge-only `strategy-test` fork (`evaluator-only/stripped-strategy-test/SKILL.md`, gitignored), the **B-1** task def (spec §4.3 exemplar), and the **B-1 golden object id** (`evaluator.toml [oracle.b_set.goldens]`, gitignored). **B-2..B-10 + their goldens are NOT provided** → M2 stays a **1-task contingency** (report it honestly; never label a 1-task percentile interval a "cluster-bootstrap CI" — D26).

Build (mirror the F-domain shape — `datasets/f_tasks.py`, `runners/f_run.py`, `experiments/m1_run.py`, report engine already renders B generically):
1. **Per-run isolation (D20):** `run_uid` save name `<model>-<condition>-<run_id>` (records already have `run_uid`, format `f"{condition_id}__{run_index:04d}"`); preflight-assert the target folder/name is empty; on save capture the created object id; delete/reset after grading.
2. **Stripped strategy-test loader (§18.9, D27):** load `evaluator.toml [skill] strategy_test_path`, inject as system prompt for the **B-skill** arm only (B-noskill gets nothing). The fork is already stripped+staged; the loader just reads it. Model lazy-loads `domain-skills/` via `bash $SKILL_PATH`.
3. **playwright-cli readback oracle (§18.7), evaluator creds:** navigate run folder → open object by captured id → run → verify executed grid vs the evaluator-only golden under prompt=South. **Three checks:** (1) captured object exists in run folder; (2) definition = source cube `Query_CharacteristicValue_Mandatory`, Rows ⊇ {Years Hierarchy, Region}, Cols ⊇ {Cost}, prompt=South; (3) executed grid == golden grid under prompt=South. Golden-discriminating: correct ⇒ PASS; wrong cube/rows/cols/prompt ⇒ FAIL.
4. **Wire B into `run-m1`:** `cli._load_m1_domain_tasks` add `"B"`; `m1_run.run_m1` B branch; `build_b_tasks(B-1)`. Report renders B (cluster bootstrap; 1-task contingency).
5. **M2 (D25):** B-noskill vs B-skill — same task, the only difference is the stripped-skill injection; both instrumented identically by the harness.

**TESTS MUST BE DETERMINISTIC** — stub the playwright-cli/MSTR client (no live infra in the suite). Like F1/F2, guard any node/store-dependent tests with `requires_node`/`requires_store` skipif so CI (which lacks node + the gitignored golden store) SKIPS them, not fails. Live readback is exercised only in the deferred execute.

## 3. Integrity invariants (NEVER relax — repo is PUBLIC) — and the 2 traps that already bit
- Creds / MSTR host / golden object id live ONLY in gitignored `evaluator.toml` + `.env` + `evaluator-only/`. Confirmed gitignored: `/reports/`, `/evaluator-only/`, `evaluator.toml`, `.env`.
- **TRAP 1 (hit in 009): golden answer in a tracked file.** Before EVERY ship, `git grep` the tracked tree (`-- src tests`) for ALL golden tokens — use a COMPLETE token set (the 009 incomplete-grep missed `analyzeFailure`/`diagResult`). For B: never let the golden object id, golden grid values, or the candidate's expected solution appear in any tracked file. Mutant/golden fixtures → gitignored `evaluator-only/` only.
- **TRAP 2 (hit in 009): candidate prompt leaks the answer.** The B-1 task prompt must describe the task at a fair bug-report/feature-request level (§4.1 withhold-localization) — do NOT name golden object ids or hand over the exact solution. The candidate MSTR account must not be able to read the golden (D19/D20).
- Candidate workspace/account never reaches any golden/oracle/object-id (D19/D33).

## 4. Where to resume
- **Branch:** `feat/agentic-v1-010-b-domain-m2` (off main, has 008+009+CI-fix; carries the tracker/runbook commits). Pull main first if stale.
- **Recreate the per-phase task graph** for 010 (task ids don't persist): `010-{spec,grill,plan,branch,impl,drift,ship,verify,pr-review,fix,merge}` with blockedBy edges per the autodev SKILL.md. spec/grill are ⏭️ pre-completed; branch is done.
- **Start at 010-spec:** author `items/010-spec.md` from §4.3/§18.7–18.9 + `items/010-b-domain-artifacts.md` (orchestrator writes it — spec phase is ⏭️). Then dispatch the **Opus** plan subagent (reads the spec + the staged artifacts + the F-domain code to mirror) → `items/010-plan.md`. Then Sonnet impl → drift → tier-2 ship → verify ‖ pr-review → fix → squash-merge.

## 5. Deferred live execute (do NOT run unless asked) — see `EXECUTE-DEFERRED.md`
- **D k=5 roster** (6 arms; ~8–15h): a stall-watchdog script (kills an arm only on 20m of no output-file growth). Partial deepseek data from the stopped run is in gitignored `/reports/agentic-v1/runs-dset-deepseek-deepseek-v4-pro.jsonl`.
- **F candidate runs:** ⚠️ first complete the **`condition_id` wiring** (`items/009-plan.md §Execute-phase follow-ups`) so F outcomes attribute per arm.
- **B/M2 runs:** after 010 merges; live MSTR.
- **Final report:** `report-m1` over the landed D(+F+B) arms (command in `EXECUTE-DEFERRED.md`). M1 spec frozen at `spec_hash ca4467f2…` (`reports/agentic-v1/M1-spec.frozen.json`).

## 6. Env (every run)
```bash
cd ~/Documents/Repository/agent-eval-lab
export PATH="/opt/homebrew/bin:$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"   # timeout + node>=20
set -a; . ./.env; set +a                                                       # cloud keys + CMC_DOCS_URL
uv run pytest -q -p no:cacheprovider
uv run ruff check . && uv run ruff format --check .                            # WHOLE repo (CI parity)
```
Known: a few oracle-subprocess timeout tests in `tests/runners/test_pytest_edge.py` / golden-conformance are **pre-existing flakes** (pass in isolation) — don't chase them; confirm any failure is only there.

## 7. Lessons from 008/009 (apply to 010)
- The **review + pr-review gates caught real defects every time** (008: a latent `run-dset` TransportError crash on the live path; 009: a golden leak + an oracle false-negative). Trust the loop; verify findings directly before fixing AND before dismissing.
- **Run `ruff format --check .` (whole repo), not just `src tests`** before every push (CI parity).
- For golden-dependent tests: **guard with `requires_node`/`requires_store`** so CI skips (not fails).
