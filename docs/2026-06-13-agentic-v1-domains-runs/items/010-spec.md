# 010 — B-domain adapter + M2 (skill-effect) — SPEC

**Status:** spec phase ⏭️ PRE-COMPLETED — this file is orchestrator-authored from the frozen
source spec (`docs/superpowers/specs/2026-06-12-use-case-agentic-eval-design.md` §4.3, §6, §7,
§18.7–18.9; decisions D19/D20/D25/D26/D27/D33/D37) + the staged owner artifacts
(`items/010-b-domain-artifacts.md`). No brainstorming/grill dispatch — the source spec is the
output of 3 review rounds + the 2026-06-13 grill. **CODE ONLY; all live MSTR runs are DEFERRED**
(`EXECUTE-DEFERRED.md`).

## Goal

Add the **Browser set (B)** domain adapter to the eval lab, mirroring the F-domain shape, so that
M1 can run B tasks and **M2** (the skill-effect controlled experiment) can compare a **B-noskill**
arm against a **B-skill** arm. B grades a long-horizon MicroStrategy Library GUI automation task
(`playwright-cli`) by an **evaluator-credentialed readback oracle** against an evaluator-only
golden. The candidate never sees the golden (D19/D33).

Everything is built so the **tests are fully deterministic** (the MSTR/`playwright-cli` client is
stubbed; no live infra in the suite) and the **live readback is exercised only in the deferred
execute**. Node/store-dependent tests are guarded with `requires_node`/`requires_store` skipif so
CI (which lacks node + the gitignored golden store) **SKIPS** them, never fails.

## Scope (what 010 builds — code only)

Owner artifacts STAGED (gitignored): candidate MSTR account (`evaluator.toml [candidate]`,
least-priv, ≠ evaluator `mstr1`, cannot read the golden), the stripped knowledge-only
`strategy-test` fork (`evaluator-only/stripped-strategy-test/SKILL.md`), the **B-1** task def
(source spec §4.3 exemplar), and the **B-1 golden object id** (`evaluator.toml
[oracle.b_set.goldens]` key `"B-1"` + `[oracle.b_set] project_id`). **B-2..B-10 task defs + their
goldens are NOT provided** → M2 stays a **1-task contingency** (report honestly; NEVER label a
1-task percentile interval a "cluster-bootstrap CI" — D26/§8).

1. **Per-run isolation (D20).** Save name `<model>-<condition>-<run_id>` derived from the record's
   `run_uid` (the isolation primitive already on `Trajectory.run_uid`, format
   `f"{condition_id}__{run_index:04d}"`). Preflight-assert the target folder/name is **empty**; on
   save **capture the created object id**; **delete/reset** the created object after grading. The
   grader keys on the **captured object id**, never a name search.
2. **Stripped strategy-test loader (§18.9, D27).** Read `evaluator.toml [skill] strategy_test_path`
   and inject the stripped `SKILL.md` as a system prompt for the **B-skill arm only**; **B-noskill
   gets nothing**. The fork is already stripped + staged; the loader only reads it. The model
   lazy-loads `domain-skills/` via `bash $SKILL_PATH` (no special tool).
3. **`playwright-cli` readback oracle (§18.7), evaluator credentials.** Navigate the run folder →
   open the captured object id → run it → verify the executed grid against the evaluator-only
   golden under prompt = South. **Three checks (golden-discriminating):**
   1. the captured object exists in the run folder;
   2. definition = source cube `Query_CharacteristicValue_Mandatory`, Rows ⊇ {Years Hierarchy,
      Region}, Columns ⊇ {Cost}, prompt = South;
   3. executed grid == evaluator-only golden grid under prompt = South.
   Correct ⇒ PASS; wrong cube / wrong rows / wrong cols / wrong prompt ⇒ FAIL. The oracle is a
   **pure grader over a readback result struct**; the live readback I/O is a thin, **injectable**
   client (stubbed in tests).
4. **Wire B into `run-m1`.** Extend `cli._load_m1_domain_tasks` to add `"B"`; add the B branch to
   `experiments/m1_run.run_m1` (mirroring the F branch — absent tasks ⇒ skipped, never a crash);
   `build_b_tasks(B-1)` assembles the candidate-visible B-1 Task paired with its held-out oracle.
   The report engine already renders B generically (`reports/m1._DOMAINS = ("F","D","B")`).
5. **M2 (D25/D37).** B-noskill vs B-skill — **same task**, the only difference is the stripped-skill
   injection (item 2). **Both arms are instrumented identically by the harness** (§7); the skill's
   own cost/usage machinery is removed from the arm, not cross-checked. The estimand is the
   **bundled stripped-skill effect** (D37), never "domain knowledge alone".

### Config plumbing (extend `experiments/evaluator_config.py`)

`load_evaluator_config` currently ignores the B extras (confirmed by the in-file comment). 010
extends it to parse, as frozen dataclasses:
- a typed **`CandidateConfig`** for `[candidate]` (least-priv MSTR account fields);
- `[oracle.b_set] project_id` on `OracleBSetConfig`;
- `[oracle.b_set.goldens]` (a `dict[str, str]` of task-id → golden object id) on `OracleBSetConfig`.

Missing-section/missing-key errors keep the existing clear-`ValueError` discipline. Real values
live **only** in the gitignored `evaluator.toml` — never echoed into a tracked file or test.

## Acceptance criteria

- `uv run pytest -q -p no:cacheprovider` green (pre-existing oracle-subprocess timeout flakes in
  `tests/runners/test_pytest_edge.py` / golden-conformance excepted — confirm any failure reproduces
  on base without the 010 diff).
- `uv run ruff check .` **and** `uv run ruff format --check .` clean over the **WHOLE repo** (CI
  parity — the #20 hotfix gap).
- **B-1 oracle discriminates:** golden-correct readback ⇒ PASS; each of {wrong cube, missing a
  required row, missing the Cost column, wrong prompt} ⇒ FAIL. At least one negative fixture per
  failure mode (D24 contradiction checks). Mutant/golden fixtures live in **gitignored
  `evaluator-only/`** only.
- **B arms wired:** `run_m1` produces B outcomes for both a noskill and a skill condition with the
  stubbed client; the stripped-skill system prompt is present for B-skill and absent for B-noskill.
- **Per-run isolation:** preflight-absence assert fires when the target name is occupied; the
  captured object id (not a name search) is what the grader reads; reset/cleanup runs after grading.
- **Deterministic tests:** every test that would touch live MSTR / `playwright-cli` / node / the
  golden store is either fully stubbed or guarded with `requires_node`/`requires_store` so CI skips.
- **Integrity (PUBLIC repo):** complete-token `git grep` over the tracked tree (`-- src tests`)
  finds **zero** golden object ids, golden grid values, project ids, candidate creds, MSTR host, or
  the candidate's expected solution. The B-1 candidate prompt describes the task at a fair
  bug-report/feature-request level (§4.1 withhold-localization) — it does NOT name the golden
  object id or hand over the exact solution.

## Out of scope (explicit)

- **All live MSTR runs** (B-noskill/B-skill execution, the readback against the live Intelligence
  Server, the M2 comparison over real arms) — DEFERRED to the owner (`EXECUTE-DEFERRED.md`). 010
  ships the machinery; the deterministic verify uses the stubbed client.
- **B-2..B-10 task defs + their goldens** — NOT provided. M2 over B-1 is a 1-task contingency.
  Mark B-2..B-10 BLOCKED in PROGRESS/SKIPPED. The ≥10-task cluster bootstrap is NOT claimed.
- REST readback (§18.7 says REST deferred — `playwright-cli` readback only).
- Records/runner schema changes (landed in 008 — `run_uid` already exists).

## Integrity invariants (NEVER relax — repo is PUBLIC) + the 2 traps that already bit

- Creds / MSTR host / golden object id / project id / golden grid live ONLY in gitignored
  `evaluator.toml` + `.env` + `evaluator-only/`. Confirmed gitignored: `/reports/`,
  `/evaluator-only/`, `evaluator.toml`, `.env`.
- **TRAP 1 (hit in 009): golden answer in a tracked file.** Before ship, `git grep` the tracked
  tree for a COMPLETE token set (the 009 incomplete grep missed `analyzeFailure`/`diagResult`).
  Mutant/golden fixtures → gitignored `evaluator-only/` only.
- **TRAP 2 (hit in 009): candidate prompt leaks the answer.** The B-1 prompt stays at problem
  level; never names the golden object id or the exact solution. The candidate account cannot read
  the golden (D19/D20/D33).

## References

- Source spec §4.3 (B-set exemplar B-1 + two variants), §6 (validity mask), §7 (records/runner),
  §18.7 (B-set oracle), §18.8 (B-task independence), §18.9 (stripped skill fork).
- Decisions: D19 (integrity boundary), D20 (per-run isolation), D25 (M2 controlled), D26 (≥10
  tasks / never mislabel a low-cluster CI), D27 (knowledge-only = stripped fork), D33 (fs/process
  isolation, not just gitignore), D37 (bundled-skill estimand).
- Owner artifacts + buildable-now matrix: `items/010-b-domain-artifacts.md`.
- Mirror shape: `datasets/f_tasks.py`, `datasets/f1_oracle.py`, `runners/f_run.py`,
  `experiments/m1_run.py`, `cli._load_m1_domain_tasks`, `experiments/evaluator_config.py`.
- Tier-2 ship contract: `items/008-ship.md`, `items/009-ship.md`.
