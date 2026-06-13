# MASTER-PLAN — agentic_v1 eval foundation

- **Mode:** backlog (the §16 6-package decomposition as dependency-ordered items). Per-item
  **brainstorming + grill are PRE-COMPLETED ⏭️** — the source spec is the output of 3 review
  rounds + the 2026-06-13 grill session (§15/§15a/§15b/§18). The orchestrator does NOT re-invoke
  brainstorming/grill; each item-spec is derived from its source-spec section.
- **PR shape:** **Consolidated (user-chosen 2026-06-13).** Build all 7 items on the feature branch
  with per-item TDD + drift + **/code-review + /verify** gates (durable commits + verdict files);
  each item's sub-branch is **squash-merged into the feature branch locally** after its gates pass.
  Push ONCE and open a **single feature-branch PR into main** at the end (Phase 3) for the user to
  merge. No per-item GitHub PRs, no intermediate pushes. (This is an explicit user opt-in to a
  bundled cadence; per-item review rigor is preserved via /code-review on each item's diff.)
  Per-item gate set: drift → (/code-review ‖ /verify) → fix → local squash-merge into feature branch.
- **Project type:** non-web (Python eval library) → **Verify** (not QA) on every item.
- **Feature branch:** `autodev/agentic-v1-eval-foundation`, cut off `docs/hard-substrate-phase-spec`
  (which carries the spec + committed datasets). Sub-branches `feat/agentic-v1-<id>-<slug>` → PR
  into the feature branch → squash-merge. Feature branch left OPEN at the end for the user to PR to main.
- **Protected branches:** never auto-merge to `main`/`m2021`. No opt-in given this turn.
- **Models per dispatch:** plan → Fable; impl/drift/verify/review/pr-review/fix → Sonnet. Orchestrator = session default.
- **Test discipline:** TDD (red-green-refactor) per CLAUDE.md; tests mirror src (`tests/<pkg>/test_<mod>.py`), pytest, `uv run pytest`.
- **Env for live arms:** `set -a; . ./.env; set +a` + `export PATH="$HOME/.nvm/versions/node/v22.22.2/bin:$PATH"`.

## Items (dependency order)

| # | id | Package | Status | Depends |
|---|----|---------|--------|---------|
| 1 | 001-records-runner | Records+runner revision + fc-v3 (§7/§18.1) | IN | — |
| 2 | 002-experiment-types | experiments/ types + evaluator.toml + freeze-spec + check-env (§18.3/§8) | IN | 001 |
| 3 | 003-f3-oracle | F3 oracle, ≥3 fixtures, contradiction checks (§18.6) | IN (golden staged) | 002 |
| 4 | 004-repo-adapter | Isolated candidate workspace + wdio edge + F1/F2 oracles (§4.1) | IN (golden staged) | 003 |
| 5 | 005-dset-harness | playwright-cli agent + D-set browse + fact-key grading (§4.2/§18.10) | IN (docs live, answers staged) | 002 |
| 6 | 006-bset-harness | B-set isolation + MSTR readback oracle + stripped skill fork (§4.3/§18.7/§18.9) | IN-CODE; RUN B-1 only | 005 |
| 7 | 007-m1-m2-reports | Per-domain+macro aggregation + Pareto + fc-v3 + freeze-spec + **RUN M1 + FINAL REPORT** (§8) | IN (B-domain/M2 partial) | 001,002,003,004,005,006 |

## Deliverable
Item 007 produces `reports/agentic-v1/M1-final-report.md` — the user's requested final report:
per-domain F/D-scores (+ B-1) with CIs, macro composite, Pareto (success vs cost/rounds/tokens),
fc-v3 taxonomy, validity mask + invalid-rates, over the reachable models. M2/B-domain coverage
documented honestly (partial). The report grows as owner unblocks B-2..B-10.

## Run convention
After each item phase passes its gate, mark the PROGRESS.md cell ✅ and the TaskCreate task
`completed`. Resume from PROGRESS.md on a fresh session. `.autodev-current` points here.
