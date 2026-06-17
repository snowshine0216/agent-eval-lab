# Agent Eval Lab — Design: B-1 Live Spike (human-scored)

- **Date:** 2026-06-17
- **Status:** Approved + grilled (grill-with-docs, 2026-06-17) — ready for writing-plans.
  Eight decisions resolved against CONTEXT.md (§13).
- **Scope:** A single-task (B-1) vertical slice of the B-domain (MicroStrategy Library
  browser automation) that drives the candidate **live** to build the report, records its
  trajectory + cost, and grades it **by human review** against a fixed rubric. Both M2 arms
  (noskill / skill), **k = 3** valid trials per model, **50-round** cap. Models: qwen-max,
  deepseek, MiniMax-M3 (chat-loop) + `claude -p` (subprocess). **Build + test now; live
  execution deferred to the owner.**
- **Parent spec:** [2026-06-12-use-case-agentic-eval-design.md](2026-06-12-use-case-agentic-eval-design.md)
  (§4.3 B-set, §18 implementation parameters). This is the EXECUTE phase for B, scoped to
  B-1, with the live evaluator readback **deferred** and replaced by human scoring.
- **Supersedes for B-1 only:** the EXECUTE-DEFERRED steps 1–4 in
  [docs/2026-06-13-agentic-v1-domains-runs/EXECUTE-DEFERRED.md](../../2026-06-13-agentic-v1-domains-runs/EXECUTE-DEFERRED.md)
  §3, with two deliberate spike deviations recorded in §9.

---

## 1. Purpose

Answer one question on one real task: **how reliably, and at what cost, can each candidate
model build the B-1 MicroStrategy Library report by driving `playwright-cli` headless — and
does the stripped `strategy-test` skill change that?** This is a spike: it retires the
biggest unknown (can a model drive the MSTR Library SPA end-to-end at all?) and produces a
first per-model browse-reliability + efficiency read, scored by the owner rather than by an
automated oracle.

It is **not** the full B-domain: no ≥10-task cluster bootstrap, no automated readback, no
exact-grid compare. Those stay deferred (§9).

## 2. What carries over, what changes

**Carries over:** the per-run isolation primitives (`runners/b_isolation.py` —
`save_name_from_run_uid`); the two-arm M2 task pair (`datasets/b_tasks.py`); the candidate
chat-loop (`run_single` + `BROWSE_TOOLS` + `bash_edge`, the D-set browse runtime); the
standalone per-arm driver shape proven by `run-f` (`_run_f_command`); the `claude -p`
subprocess harness building blocks (`runners/claude_cli_candidate.py`); the censoring
contract + `Trajectory` efficiency fields (rounds/tokens/cost/wall-time, item 001); the
env-validity mask + D34 replacement loop (env axis); the pricing snapshot
(`evaluator-only/pricing.json`).

**Changes (this spike):**
- The **grade is an owner verdict** (§4) — *human-performed outcome verification*. The live
  `MstrReadbackClient` readback is NOT implemented; the owner validates each saved object in
  MSTR against the **definition-match checklist** (CONTEXT.md: *definition-match checklist*,
  *owner verdict* — never "rubric", which is reserved).
- A **verdict sheet** is emitted after the live run; a pure `report-b` step joins the owner
  verdicts with the recorded trials to build grades and metrics.
- A new **`run-b`** CLI command (standalone, per model × arm), mirroring `run-f` — NOT the
  `run-m1` orchestrator (which re-runs D and F every invocation).
- The spike is **unregistered/descriptive** — no `freeze-spec`, no `ExperimentSpec`,
  no `spec_hash` (like the `run-f-claude-baseline`). Its numbers are SPIKE findings, **not**
  a pre-registered M1/M2 result.

## 3. Approach (selected: A)

**A — standalone `run-b` driver + injected candidate-driver callback + owner verdict.**
Considered and rejected: **B** (wire the live `b_client` into `run-m1` — rejected: `run-m1`
re-runs D + F every invocation and couples B to whole-roster orchestration); **C**
(candidate-only, no recorded grade — rejected: the owner chose definition-match grading, so
the checklist + verdict pipeline must exist).

### 3.1 Three phases

```
Phase 1 (automated, owner runs live)   Phase 2 (owner, manual)   Phase 3 (automated, pure)
run-b: candidate builds the object,    validate each saved       report-b: owner verdicts + trials
records evidence + emits a verdict     object against the         → pass_at_1 (headline) + pass_pow_3
sheet                                  definition-match checklist / efficiency / skill delta
```

## 4. The grade — owner verdict against the definition-match checklist

The spike grade is **human-performed outcome verification** (grading the reached world-state,
the `FinalStateSpec` sense, performed manually). After the live run, the owner opens each
saved object in MSTR and records an **owner verdict** (`PASS | FAIL | INVALID`) against the
**B-1 definition-match checklist** (the definition-match grade from the parent spec, minus the
exact-grid compare). "Rubric" is deliberately avoided — it is reserved (CONTEXT.md:
*Judge rubric*, *VerificationSpec*, *review*); this is a **checklist**, not a rubric.

> **B-1 definition-match checklist.** A trial **PASSES** iff all five hold:
> - **R1** — an object exists, saved under the instructed unique name, in the candidate folder.
> - **R2** — source dataset = **SAPBW › AV_TUTO › Query_CharacteristicValue_Mandatory**.
> - **R3** — **Rows** include **Years Hierarchy** *and* **Region**.
> - **R4** — **Columns** include **Cost**.
> - **R5** — the mandatory prompt is answered **South** and the report renders the prompted result.
>
> **PASS** = R1 ∧ R2 ∧ R3 ∧ R4 ∧ R5. Otherwise **FAIL**. **INVALID** (env/provider failure)
> is auto-tagged by the runner; the owner may override a verdict to INVALID.

Exact executed-grid equality (parent spec §18.7 / ADR-0014) is **out of scope** for the spike.

## 5. Components

All new modules are small, pure where possible, and mirror existing patterns. I/O stays at
the edges (runner + CLI).

| Module | Kind | Purpose |
|---|---|---|
| `records/b_trial.py` | pure | The **`BTrial`** record: `run_uid`, `condition_id`, `task_id` (the arm), `save_name`, `folder`, `Trajectory`, `invalid: bool`, `invalid_reason`. **No `GradeResult`** — the grade is the later **owner verdict** (CONTEXT.md). Frozen, serializable; the on-disk unit of `trials-b-*.jsonl`. |
| `runners/b_live.py` | edge | B trial lifecycle + per-arm k-valid loop. Per trial: derive the **task-scoped** `run_uid` → save-name → call injected `candidate_run_fn(task, run_index, save_name) → Trajectory` → auto-tag env/provider **invalid** → wrap as a `BTrial` (no grade). Runs to **k=3 valid** trials with env-invalid replacement via the shared VOID helper. |
| `runners/b_candidate_chat.py` | edge | `make_b_chat_run_fn(config, http_client, temperature, max_tokens, condition_id, …)` → the chat-loop candidate driver for qwen-max/deepseek/MiniMax: a per-trial isolated playwright-cli session + workdir (`make_bash_executor`, allowlist-confined to `playwright-cli`), `run_single` + `BROWSE_TOOLS`, **max_rounds = 50**. |
| `runners/bash_edge.py` | edge | Add a **`file:`-scheme reject** in `parse_argv` (a `playwright-cli open file:///…` argument is refused) so the chat-loop candidate cannot read local files via browser `file://` navigation (§7). Pure, ~3 lines + test. |
| `runners/b_candidate_claude.py` | edge | `make_b_claude_run_fn(model, run_subprocess, workdir_factory, …)` → the `claude -p` candidate driver: **Bash** + `playwright-cli` on PATH, reusing `claude_cli_candidate` building blocks (`build_claude_argv` browser surface, `parse_claude_result`, `_sanitized_env`). Same callback signature as the chat driver. **Not OS-confined** — see §7 residual limitation. |
| `runners/multi_run.py` | edge | Extract the D34 VOID/replacement arithmetic from `run_task_k_valid` into a generic `run_trials_k_valid(trial_fn, k_valid, max_invalid_rate, is_invalid_fn)` helper; `run_task_k_valid` is refactored to call it (behavior-preserving), and `b_live` reuses it. The subtle VOID math lives in exactly one place. |
| `datasets/b_tasks.py` | pure | Add `render_b_prompt(base_user, *, save_name, login, folder)` — inject the per-trial save-name + candidate login (app URL / user / pass) + target folder into the static B-1 user prompt. The existing two-arm `build_b_tasks` is unchanged. |
| `reports/b_scoring.py` | pure | `emit_verdict_sheet(trials) → (markdown, csv)` — the **verdict sheet**: the definition-match checklist on top, one row per trial (model, arm, trial, instructed save-name, folder, stop_reason — incl. **`max_rounds` (censored)** flagged distinctly, rounds, tokens, cost, wall-time, candidate final-message excerpt, transcript path) + a **blank verdict column**. Distinct from the blind **annotation packet** (judge calibration) — the owner inspects the live MSTR object, so the sheet is not blind. |
| `reports/b_report.py` | pure | `report_b(trials, verdicts) → BReport` — joins each `BTrial` with its **owner verdict** to build a `GradeResult`+`RunResult` purely, then per (model, arm): **headline `pass_at_1`** (per-trial pass rate), secondary `pass_pow_3`, valid/invalid/void counts, mean+median rounds/tokens/cost/wall-time; plus the descriptive **skill delta** on `pass_at_1` (skill − noskill) per model. `claude -p` is a **peer on success** but **flagged on efficiency** (its column reads "turns (Claude Code)" / "USD (subscription-equiv)", never pooled into the chat-model rounds/cost ranking). |
| `experiments/evaluator_config.py` | edge | Extend the typed config: candidate-facing `[candidate] app_url` + `[candidate] folder` (the save target); `[candidate] password` is read (owner fills it before the live run). |
| `cli.py` | edge | New **`run-b`** command — one model per invocation, `--arm {noskill,skill,both}` (default `both`); mirrors `_run_f_command`. Incremental `trials-b-<slug>-<task_id>.jsonl` writes (`BTrial`, **not** `RunResult`) + `.void.json` sidecar + the verdict sheet; auth/quota fail-fast (HTTP 401/403) + `TransportError` handling. New **`report-b`** command (pure: `BTrial`s + owner-verdicts JSON → report). |

The live `MstrReadbackClient` implementation is **not built** this spike. The Protocol and the
existing fake-backed `run_b` / `b1_oracle` / `b_isolation` machinery are left in place,
unused by the live path.

## 6. Data flow (one trial)

1. **Task-scoped** `run_uid = f"{condition_id}__{task_id}__{run_index:04d}"` where `task_id`
   is the arm (`b-b1-noskill` / `b-b1-skill`); `save_name = save_name_from_run_uid(run_uid)`
   (reuses `runners/b_isolation.py`) → e.g. `dashscope-qwen3.7-max__b-b1-noskill__0002`. A
   non-task-scoped uid is invalid (CONTEXT.md: *run_uid* — collides across tasks).
2. The candidate driver renders the prompt (`render_b_prompt`), logs in as the least-priv
   candidate account (`bxu`), builds the report, and saves it under **exactly** `save_name`
   in the candidate folder. The full `Trajectory` is recorded (rounds/tokens/cost/wall-time).
3. The trial is auto-tagged **invalid** iff the model call was a provider failure
   (`is_env_invalid_run` — 401/403/empty-choices) **or** the health probe (pre/post POST to
   `[health_probe] url`) reports env-unhealthy. Invalid → a replacement trial runs (D34, env
   axis only). A `max_rounds`/`safety_cap` stop is **censored** (a task failure for the verdict,
   surfaced distinctly), **not** invalid.
4. Persist a grade-less `BTrial` (model, arm, run_uid, save-name, folder, stop_reason,
   rounds, tokens, cost, wall-time, candidate final message, transcript path, invalid flag).
5. After all arms × trials: emit `trials-b-<slug>-<task_id>.jsonl` + the verdict sheet
   `b1-verdict-sheet-<slug>.{md,csv}`.

Cost (recorded for later `report-b` use): chat-loop models → tokens × `pricing.json`;
`claude -p` → `total_cost_usd` (subscription-equivalent). Rounds: `Trajectory.rounds` (chat)
/ `num_turns` (claude) — kept on separate axes in the report (§5, `b_report`).

## 7. Integrity boundary (D19 / D33)

The candidate must NOT reach `evaluator.toml` or `evaluator-only/` — they hold the MSTR
project id, the (eventual) golden object id, and the evaluator credentials. Confinement
**differs by driver**, and the spike accepts one documented residual gap:

- **Chat-loop path — strongly confined.** `bash_edge` runs an **allowlist of exactly
  `{"playwright-cli"}`**, no shell, from-scratch env, bare-name argv only — so the candidate
  cannot `cat` the store. The one residual vector is browser **`file://` navigation**
  (`playwright-cli open file:///…/evaluator.toml` + `eval`); this spike **closes it** with a
  `file:`-scheme reject in `parse_argv` (§5).
- **`claude -p` path — NOT OS-confined (documented residual limitation).** For B it needs
  native **Bash** + the **real HOME** (OAuth in Keychain), so it could read the store via an
  absolute path. Closing this properly needs OS-level isolation (seatbelt/restricted user) and
  is **deferred to the production B runner**. For the spike it is **mitigated, not closed**:
  (1) the evaluator store + `evaluator.toml` are **relocated out of the repo tree** for live
  runs (so a naive `./evaluator.toml` read fails); `run-b` reads the config at startup as the
  *harness*, never exposing it to the candidate session; (2) the spike's grade does not use the
  golden grid and the evaluator creds are a disposable test account. The residual limitation is
  recorded loudly, like the trusted **sandbox**'s documented temp-dir-level limitation.

The candidate account `bxu` must itself be unable to read the golden objects
(owner-confirmed precondition). The boundary intent stays intact so the future automated
runner inherits a clean story.

**Shared candidate account (decided 2026-06-17).** All models and both arms log in with the
**single** least-priv `[candidate]` account (`bxu`); isolation is by the **unique per-trial
save-name** (which encodes model + arm + trial — e.g. `dashscope-qwen3.7-max__b-b1-noskill__0002`),
not by a distinct account per model. This is D19/D20-consistent (least-priv + can't-read-goldens
+ per-run isolation — *not* per-model accounts) and keeps every saved object collision-free and
attributable for the owner's manual review. Consequences: (1) `run-b` invocations are run
**sequentially** — never two models in parallel on the one login (concurrent MSTR sessions for
one user can collide on save/prompt state); (2) each trial still opens a **fresh playwright-cli
browser session** so a mandatory-prompt answer never bleeds between trials; (3) the shared
folder accumulates every trial's object — desirable for review, attributable by name.

## 8. Testing

Everything is unit-tested with **no live MSTR and no live provider**:
- `candidate_run_fn` is injected; tests pass a fake returning a canned `Trajectory`
  (success, failure, env-invalid, safety-cap, max-rounds variants).
- The `claude -p` path injects a fake `run_subprocess` (canned stdout JSON), as
  `claude_cli_candidate` tests already do.
- Pure tests: task-scoped `run_uid` → `save_name_from_run_uid` round-trip; `render_b_prompt`
  substitution + that it never leaks evaluator creds; invalid-tagging (provider/env) vs
  censoring (max_rounds/safety_cap — failure, not invalid); `run_trials_k_valid`
  VOID/replacement arithmetic (behavior parity with the old `run_task_k_valid`);
  `emit_verdict_sheet` shape (incl. the censored-stop flag); `report_b` headline `pass_at_1` +
  `pass_pow_3` + efficiency + skill-delta, and `claude -p` efficiency rendered on its own axis.
- `parse_argv` rejects a `file:`-scheme `playwright-cli` argument (chat-loop `file://` guard).
- Integrity guard: the candidate prompt + workdir cannot reference the evaluator store path,
  and `bash_edge`'s allowlist rejects any non-`playwright-cli` binary (§7).

## 9. Deferred / out of scope

- **Live `MstrReadbackClient`** (evaluator-credentialed readback) + automated definition
  extraction + **exact-grid compare** — replaced by human scoring this spike.
- **B-2 … B-10** task definitions + goldens; therefore **no cluster-bootstrap CI** — B-1 is a
  one-task contingency, reported honestly (point summary, never a CI labelled as bootstrap).
- **`run-m1` integration** — `run-b` is standalone; B stays out of the D/F re-run path.
- **REST readback** — noted in the parent spec; not built here.

- **OS-level `claude -p` confinement** — deferred to the production B runner (§7); the spike
  ships a documented residual limitation + store relocation instead.

**Three recorded deviations from the parent spec, all spike-scoped:**
1. **§18.7 readback** (frozen `playwright-cli` readback) → **owner verdict** for B-1. The
   `evaluator.toml [oracle.b_set] readback` line is left unchanged; the spike does not exercise it.
2. **§4.3 grid equality** (oracle check 3) → **dropped** for B-1 (definition-match only).
3. **§18.2 pre-registration** (frozen `ExperimentSpec`) → **not** frozen; the spike is
   unregistered/descriptive (like `run-f-claude-baseline`). Its pass-rate + skill-delta are
   SPIKE findings, never a registered M1/M2 result.

## 10. Success criteria

- `run-b` runs both arms × k=3 for one model live, producing grade-less
  `trials-b-<slug>-<task_id>.jsonl` with real efficiency fields and a
  `b1-verdict-sheet-<slug>.{md,csv}` carrying the definition-match checklist + one evidence
  row per trial (censored stops flagged distinctly).
- Env/provider failures are auto-tagged INVALID and replaced (D34, env axis); a model that
  cannot land k=3 valid trials is VOID, surfaced not silently dropped. `max_rounds`/`safety_cap`
  stops are censored task-failures, never invalid.
- The owner fills verdicts; `report-b` joins them with the trials and produces per-model×arm
  **`pass_at_1` (headline)** + `pass_pow_3` + efficiency + the descriptive skill delta, with
  `claude -p` flagged on its own efficiency axis and B-1 reported as a one-task contingency.
- The chat-loop candidate is allowlist-confined + `file://`-blocked; the `claude -p` residual
  limitation is documented and the store relocated out of the repo tree (§7).
- Full unit-test coverage with fakes; no live MSTR / provider in the test suite.

## 11. Work decomposition (for writing-plans)

1. **`run_trials_k_valid` extraction** — refactor `multi_run.py` (behavior-preserving), tests
   prove parity. *(Precondition for `b_live`.)*
2. **`BTrial` record** (`records/b_trial.py`) — grade-less, frozen, serializable.
3. **`b_live.py`** — trial lifecycle + per-arm k-valid loop over an injected `candidate_run_fn`;
   task-scoped `run_uid`; env/provider invalid-tagging; censoring (not invalid) for cap stops.
4. **`file://` guard** (`bash_edge.parse_argv`) — reject `file:`-scheme args + test.
5. **Chat candidate driver** (`b_candidate_chat.py`) + `render_b_prompt` — qwen-max / deepseek
   / MiniMax over the browse loop, max_rounds = 50, allowlist-confined workdir.
6. **`claude -p` candidate driver** (`b_candidate_claude.py`) — Bash + playwright-cli browser
   surface; reuse `claude_cli_candidate` building blocks; record num_turns / total_cost_usd.
7. **Config extension** — candidate `app_url` + `folder`; password read; **store relocated out
   of the repo tree** ([store] path) so the candidate cannot reach it.
8. **`run-b` CLI** — one model per invocation, `--arm`; incremental `trials-b-*` writes, void
   sidecar, verdict sheet, auth/quota + transport handling.
9. **`b_scoring.py`** — verdict-sheet emitter (checklist + evidence rows, censored-stop flag).
10. **`report-b` CLI + `b_report.py`** — owner-verdicts + trials → grade build → `pass_at_1`
    headline + `pass_pow_3` + efficiency + skill-delta; `claude -p` on a flagged efficiency axis.
11. **Integrity guard test** + docs: a live-run runbook (env, VPN, candidate password, store
    relocation, `playwright-cli install --skills`, **calibrate-first**: one trial → check for
    premature `max_rounds` censoring before the full 24-run sweep) appended to the agentic-v1
    run docs.

## 12. Open preconditions (owner, before the live run)

- `[candidate] password` set in `evaluator.toml` (currently empty); `bxu` confirmed
  least-privilege (cannot read goldens).
- `[candidate] app_url` set (e.g. `…/MicroStrategyLibrary/app`) and `[candidate] folder` chosen.
- Evaluator store + `evaluator.toml` **relocated out of the repo tree** ([store] path updated)
  before any `claude -p` arm runs (§7).
- MSTR Library reachable from the run host (internal labs host / VPN).
- `playwright-cli install --skills` run once on the host.
- **Calibrate first:** run one trial (one model, noskill) and confirm it does not hit
  `max_rounds` far from Save before launching the full 24-run sweep (§Q6 / runbook).

## 13. Decisions resolved in the grill (grill-with-docs, 2026-06-17)

1. **Naming.** "rubric" is reserved → the grade is an **owner verdict** (`PASS|FAIL|INVALID`)
   against the **definition-match checklist**; the grade is **human-performed outcome
   verification**. Both terms added to CONTEXT.md.
2. **`run_uid`.** Task-scoped `f"{condition_id}__{task_id}__{run_index:04d}"` (arm rides
   `task_id`), not the spec's earlier `__{arm}__` form.
3. **Trial record.** Grade-less **`BTrial`** on disk (`trials-b-*.jsonl`); `report-b` joins
   owner verdicts to build the grade purely — no fabricated `GradeResult`. **→ ADR-0021.**
4. **Pre-registration.** Unregistered/descriptive — no `freeze-spec` (like the claude baseline);
   results are SPIKE findings, not a registered M1/M2.
5. **`claude -p` comparability.** Peer on success (owner verdict); efficiency flagged on its own
   axis (turns / subscription-USD), never pooled with chat-model rounds/cost.
6. **Round cap.** Keep `max_rounds=50`; calibrate-first protocol; `report-b` surfaces
   `max_rounds` censoring distinctly (censored = task-failure, not invalid).
7. **Integrity.** Chat-loop is allowlist-confined + a new `file://` guard; `claude -p` is
   NOT OS-confined → documented residual limitation + store relocated out of the repo tree;
   true OS-level confinement deferred to the production B runner.
8. **Headline metric.** `pass_at_1` (per-trial pass rate) is the headline; `pass_pow_3` is
   secondary; the skill delta is computed on `pass_at_1`.
