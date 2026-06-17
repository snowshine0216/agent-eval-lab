# Agent Eval Lab — Design: B-1 Live Spike (human-scored)

- **Date:** 2026-06-17
- **Status:** Approved design — ready for writing-plans.
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
- The **grade is human** (§4). The live `MstrReadbackClient` readback is NOT implemented;
  the owner validates each saved object in MSTR against a fixed rubric.
- A **scoring sheet** is emitted after the live run; a pure `report-b` step turns the
  owner's verdicts into metrics.
- A new **`run-b`** CLI command (standalone, per model × arm), mirroring `run-f` — NOT the
  `run-m1` orchestrator (which re-runs D and F every invocation).

## 3. Approach (selected: A)

**A — standalone `run-b` driver + injected candidate-driver callback + human grade.**
Considered and rejected: **B** (wire the live `b_client` into `run-m1` — rejected: `run-m1`
re-runs D + F every invocation and couples B to whole-roster orchestration); **C**
(candidate-only, no recorded grade — rejected: the owner chose definition-match grading, so
the rubric + verdict pipeline must exist).

### 3.1 Three phases

```
Phase 1 (automated, owner runs live)   Phase 2 (owner, manual)   Phase 3 (automated, pure)
run-b: candidate builds the object,    validate each saved       report-b: verdicts + trajectories
records evidence + emits a scoring     object in MSTR against     → pass^3 / pass@1 / efficiency
sheet with the rubric                  the rubric (§4)            / M2 skill delta
```

## 4. The grade — human review against a fixed rubric

After the live run, the owner opens each saved object in MSTR and records a verdict against
this rubric (the **definition-match** grade from the parent spec, minus the exact-grid
compare):

> **B-1 definition-match rubric.** A trial **PASSES** iff all five hold:
> - **R1** — an object exists, saved under the instructed unique name, in the candidate folder.
> - **R2** — source dataset = **SAPBW › AV_TUTO › Query_CharacteristicValue_Mandatory**.
> - **R3** — **Rows** include **Years Hierarchy** *and* **Region**.
> - **R4** — **Columns** include **Cost**.
> - **R5** — the mandatory prompt is answered **South** and the report renders the prompted result.
>
> **PASS** = R1 ∧ R2 ∧ R3 ∧ R4 ∧ R5. Otherwise **FAIL**. **INVALID** (env/provider failure)
> is auto-tagged by the runner; the owner may override a verdict to INVALID.

Exact-grid equality (parent spec §18.7) is **out of scope** for the spike.

## 5. Components

All new modules are small, pure where possible, and mirror existing patterns. I/O stays at
the edges (runner + CLI).

| Module | Kind | Purpose |
|---|---|---|
| `runners/b_live.py` | edge | B trial lifecycle + per-arm k-valid loop. Per trial: derive unique save-name → call injected `candidate_run_fn(task, run_index, save_name) → Trajectory` → auto-tag env/provider **invalid** → wrap as a `BTrial` (no auto pass/fail). Runs to **k=3 valid** trials with env-invalid replacement via the shared VOID helper. |
| `runners/b_candidate_chat.py` | edge | `make_b_chat_run_fn(config, http_client, temperature, max_tokens, condition_id, …)` → the chat-loop candidate driver for qwen-max/deepseek/MiniMax: a per-trial isolated playwright-cli session + confined workdir (`make_bash_executor`), `run_single` + `BROWSE_TOOLS`, **max_rounds = 50**. |
| `runners/b_candidate_claude.py` | edge | `make_b_claude_run_fn(model, run_subprocess, workdir_factory, …)` → the `claude -p` candidate driver: **Bash** allowed + `playwright-cli` on PATH, reusing `claude_cli_candidate` building blocks (`build_claude_argv` with a browser surface, `parse_claude_result`, `_sanitized_env`). Same callback signature as the chat driver. |
| `runners/multi_run.py` | edge | Extract the D34 VOID/replacement arithmetic from `run_task_k_valid` into a generic `run_trials_k_valid(trial_fn, k_valid, max_invalid_rate, is_invalid_fn)` helper; `run_task_k_valid` is refactored to call it (behavior-preserving), and `b_live` reuses it. The subtle VOID math lives in exactly one place. |
| `datasets/b_tasks.py` | pure | Add `render_b_prompt(base_user, *, save_name, login, folder)` — inject the per-trial save-name + candidate login (URL / user / pass) + target folder into the static B-1 user prompt. The existing two-arm `build_b_tasks` is unchanged. |
| `reports/b_scoring.py` | pure | `emit_scoring_sheet(trials) → (markdown, csv)` — the rubric on top, one row per trial: model, arm, trial, instructed save-name, folder, stop_reason, rounds, tokens, cost, wall-time, candidate final-message excerpt, transcript path, **blank verdict column**. |
| `reports/b_report.py` | pure | `report_b(trials, verdicts) → BReport` — per (model, arm): pass^3, pass@1, valid/invalid/void counts, mean+median rounds/tokens/cost/wall-time; plus the **M2 skill delta** (skill − noskill) per model and per metric. |
| `experiments/evaluator_config.py` | edge | Extend the typed config: candidate-facing `[candidate] app_url` + `[candidate] folder` (the save target); `[candidate] password` is read (owner fills it before the live run). |
| `cli.py` | edge | New **`run-b`** command — one model per invocation, `--arm {noskill,skill,both}` (default `both`); mirrors `_run_f_command`. Incremental `runs-b-<slug>-<arm>.jsonl` writes + `.void.json` sidecar + the scoring sheet; auth/quota fail-fast (HTTP 401/403) + `TransportError` handling. New **`report-b`** command (pure: trajectories + verdicts JSON → report). |

The live `MstrReadbackClient` implementation is **not built** this spike. The Protocol and the
existing fake-backed `run_b` / `b1_oracle` / `b_isolation` machinery are left in place,
unused by the live path.

## 6. Data flow (one trial)

1. `run_uid = f"{condition}__{arm}__{run_index:04d}"`;
   `save_name = save_name_from_run_uid(run_uid)` (reuses `runners/b_isolation.py`).
2. The candidate driver renders the prompt (`render_b_prompt`), logs in as the least-priv
   candidate account (`bxu`), builds the report, and saves it under **exactly** `save_name`
   in the candidate folder. The full `Trajectory` is recorded (rounds/tokens/cost/wall-time).
3. The trial is auto-tagged **invalid** iff the model call was a provider failure
   (`is_env_invalid_run` — 401/403/empty-choices) **or** the health probe (pre/post POST to
   `[health_probe] url`) reports env-unhealthy. Invalid → a replacement trial runs (D34, env
   axis only).
4. Persist a `BTrial`: model, arm, trial, run_uid, instructed save-name + folder, stop_reason,
   rounds, tokens, cost, wall-time, candidate final message, transcript path.
5. After all arms × trials: emit `runs-b-<slug>-<arm>.jsonl` + `b1-scoring-<slug>.{md,csv}`.

Cost: for chat-loop models, tokens × `pricing.json` (as `report-m1` does); for `claude -p`,
`total_cost_usd` from the result JSON. Rounds: `Trajectory.rounds` (chat) / `num_turns`
(claude).

## 7. Integrity boundary (D19 / D33)

The candidate's bash / `claude -p` workdir is **confined** and must NOT be able to read
`evaluator.toml` or `evaluator-only/` — they hold the MSTR project id, the (eventual) golden
object id, and the evaluator credentials. The candidate workdir is created **outside the
repo tree**, and only the candidate's own least-priv credentials (`[candidate]`) are passed
into the prompt/session. The candidate account `bxu` must itself be unable to read the golden
objects (owner-confirmed precondition). Even though the spike's human grade does not consume
the golden, the boundary stays intact so future automated runs inherit it.

**Shared candidate account (decided 2026-06-17).** All models and both arms log in with the
**single** least-priv `[candidate]` account (`bxu`); isolation is by the **unique per-trial
save-name** (which encodes model + arm + trial — e.g. `dashscope-qwen3.7-max__noskill__0002`),
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
- Pure tests: `save_name_from_run_uid` round-trip; `render_b_prompt` substitution + that it
  never leaks evaluator creds; invalid-tagging (provider/env); `run_trials_k_valid`
  VOID/replacement arithmetic (behavior parity with the old `run_task_k_valid`);
  `emit_scoring_sheet` shape; `report_b` pass^k / pass@1 / efficiency / skill-delta.
- A regression test asserting the candidate prompt + workdir cannot reference the evaluator
  store path (integrity guard, §7).

## 9. Deferred / out of scope

- **Live `MstrReadbackClient`** (evaluator-credentialed readback) + automated definition
  extraction + **exact-grid compare** — replaced by human scoring this spike.
- **B-2 … B-10** task definitions + goldens; therefore **no cluster-bootstrap CI** — B-1 is a
  one-task contingency, reported honestly (point summary, never a CI labelled as bootstrap).
- **`run-m1` integration** — `run-b` is standalone; B stays out of the D/F re-run path.
- **REST readback** — noted in the parent spec; not built here.

**Two recorded deviations from the parent spec, both spike-scoped:**
1. **§18.7 readback** (frozen `playwright-cli` readback) → **human grade** for B-1. The
   `evaluator.toml [oracle.b_set] readback` line is left unchanged; the spike simply does not
   exercise it.
2. **§4.3 grid equality** (oracle check 3) → **dropped** for B-1 (definition-match only).

## 10. Success criteria

- `run-b` runs both arms × k=3 for one model live, producing `runs-b-<slug>-<arm>.jsonl` with
  real efficiency fields and a `b1-scoring-<slug>.{md,csv}` sheet carrying the rubric + one
  evidence row per trial.
- Env/provider failures are auto-tagged INVALID and replaced (D34, env axis); a model that
  cannot land k=3 valid trials is VOID, surfaced not silently dropped.
- The owner fills verdicts; `report-b` produces per-model×arm pass^3 / pass@1 / efficiency and
  the M2 skill delta, with B-1 reported as a one-task contingency.
- No evaluator credential, project id, or golden artifact is reachable from any candidate
  workspace, prompt, or session (§7).
- Full unit-test coverage with fakes; no live MSTR / provider in the test suite.

## 11. Work decomposition (for writing-plans)

1. **`run_trials_k_valid` extraction** — refactor `multi_run.py` (behavior-preserving), tests
   prove parity. *(Precondition for `b_live`.)*
2. **`BTrial` + `b_live.py`** — trial lifecycle + per-arm k-valid loop over an injected
   `candidate_run_fn`; env/provider invalid-tagging.
3. **Chat candidate driver** (`b_candidate_chat.py`) + `render_b_prompt` — qwen-max / deepseek
   / MiniMax over the browse loop, max_rounds = 50, confined workdir.
4. **`claude -p` candidate driver** (`b_candidate_claude.py`) — Bash + playwright-cli browser
   surface; reuse `claude_cli_candidate` building blocks.
5. **Config extension** — candidate `app_url` + `folder`; password read.
6. **`run-b` CLI** — standalone per model × arm; incremental writes, void sidecar, scoring
   sheet, auth/quota + transport handling.
7. **`b_scoring.py`** — scoring-sheet emitter (rubric + evidence rows).
8. **`report-b` CLI + `b_report.py`** — verdicts + trajectories → metrics + skill delta.
9. **Integrity guard test** + docs: a short live-run runbook (env, VPN, candidate password,
   `playwright-cli install --skills`) appended to the agentic-v1 run docs.

## 12. Open preconditions (owner, before the live run)

- `[candidate] password` set in `evaluator.toml` (currently empty); `bxu` confirmed
  least-privilege (cannot read goldens).
- MSTR Library reachable from the run host (internal labs host / VPN).
- `playwright-cli install --skills` run once on the host.
