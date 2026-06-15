# Item 003 — Arm-as-task + Factor P

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override). Authoritative source: **§B.1**, **§B.2** (arm = distinct `task_id`; task-scope
> `run_uid`), **§B.3** (Factor-P prompt block), **§11.1 / §11.4 / §11.8**, and **Part G step 3**.
> Builds directly on item 002 (recorded policy fields) and the existing F task machinery
> ([f_tasks.py](../../../src/agent_eval_lab/datasets/f_tasks.py),
> [f_candidate.py](../../../src/agent_eval_lab/runners/f_candidate.py)).

## Goal

Express the F harness-factor ablation's four **arms** as **distinct `task_id`s** — the M2 pattern
already used for B (`b-b1-noskill` / `b-b1-skill`,
[b_tasks.py:67](../../../src/agent_eval_lab/datasets/b_tasks.py:67)) — so the ablation rides the
data model the codebase already has (`task_id` is on `RunResult`, in `serialize`, and is the
`pass_pow_k` grouping key). Build the **12 F task-arms** (3 base tasks × 4 arms) and add **Factor P**
(the context-gathering prompt block). This is the single biggest simplification from the grilling
pass (§11.1): because the arm *is* the `task_id`, there is **no** `arm_id` field, **no** `ArmDef`,
**no** `ConditionDef`/`condition_id` change, and **no** report-join plumbing — `pass^k` (computed
per `task_id`) separates arms for free, and the committed frozen M1 specs keep verifying.

## Acceptance criteria

**Arm-as-task structure (§B.1 / §B.2 / §11.1):**
- [ ] For each base F task (f1, f2, f3), build **4 arm-tasks** as distinct `task_id`s, suffix-named:
  `f-f1-bare`, `f-f1-prompt`, `f-f1-feedback`, `f-f1-both` (and the f2/f3 equivalents) → **12
  task-arms total**.
- [ ] The four arm-tasks of one base task share **byte-identical `initial_state.files`** and the
  **same `verification`** (the base task's held-out `VerificationSpec`). They differ **only** in
  `messages` (Factor P) and `available_tools` (Factor V — see V-scope note below).
- [ ] Arm → factor mapping (the 2×2): `bare` = (P−, V−); `prompt` = (P+, V−); `feedback` = (P−, V+);
  `both` = (P+, V+).
- [ ] Follow the M2 mechanism in `b_tasks.py`: a shared `verification`, a shared base message/turn
  set, with the arm differences applied on top (P via system-message append; V via tool list).

**Factor P — context-gathering prompt nudges (§B.3 / §11.4):**
- [ ] A **discrete, attributable block** appended to `_EDIT_SYSTEM`
  ([f_candidate.py:51](../../../src/agent_eval_lab/runners/f_candidate.py:51)), applied to the
  `prompt` and `both` arms only. The block directs the model to: read the **body of the method a
  call/assertion depends on**; read **sibling methods** before adding one; read **local
  conventions**; read the **full target file + full visible test set** before the first edit;
  **change only what the task requires**.
- [ ] Vocabulary: use **"visible tests"** (the glossary term), not "public tests" (§11.4).
- [ ] `bare` / `feedback` arms keep the unmodified `_EDIT_SYSTEM` (no P block).
- [ ] The P block is a **named, isolated constant** so it is attributable and diff-able (not inlined
  ad-hoc into each task).

**Task-scoped `run_uid` (§B.2 / §11.8):**
- [ ] `run_uid` becomes **task-scoped**: `{condition_id}__{task_id}__{run_index}` (replacing the
  current literal `f"{condition_id}__f__{run_index:04d}"` at
  [f_candidate.py:156](../../../src/agent_eval_lab/runners/f_candidate.py:156)). Required now that 12
  task-arms share a single condition's run space — the old `__f__` literal would collide across
  arms.
- [ ] `run_uid` uniqueness holds across (condition × 12 task-arms × run_index); add a test asserting
  no collision within a condition's run space.
- [ ] Existing `run_uid` consumers stay correct: `hydrate.py` (locate-by-`run_uid`),
  `b_isolation.save_name_from_run_uid` (B path — unaffected by the F change but confirm the slug
  derivation still holds for the new shape), `serialize` round-trip.

**No new record/spec plumbing (§B.2 / §10.1 / §10.2 / §10.5 — explicitly *not* done):**
- [ ] **No `arm_id`** field on `RunResult`/`Trajectory`/serialize. **No `ArmDef`.** **No
  `tool_set_hash`.** **No `ConditionDef`/`ExperimentSpec` change.** `condition_id` stays
  `provider:model` (so `prices[condition_id]` resolves and pricing is untouched).
- [ ] Confirm the committed frozen M1 specs still verify: `verify_spec_hash` passes (nothing touches
  the hashed schema).
- [ ] `report-m1`'s `_load_run_results` already groups by `task_id` — confirm (don't change) that
  per-arm `pass^k` falls out with **no report-side plumbing**.

## Non-goals (deferred to later items / out of run scope)
- **Factor V executor + sandbox (item 005):** `runners/sandboxed_node_edge.py`, the seatbelt
  confined-execution profile, `make_authored_test_executor`, and the tail-aware feedback rendering
  are **item 005**. Item 003 establishes the arm *identity* and the V arms' tool surface only — the
  V arms (`feedback`, `both`) declare their intent to use a V-specific `run_tests`, but the live
  sandboxed executor and the world-binding resolution that makes `run_tests` actually run authored
  tests are built in 005. The exact mechanics of how 003 represents the not-yet-wired V tool
  (placeholder vs. deferred binding) is a **plan-phase judgment call** — it must leave `bare`/
  `prompt` fully runnable today and must not fabricate a working V loop. The V-specific
  node-accurate `run_tests` `ToolDef` (§10.8) is part of item 005 unless the plan finds it must be
  defined here to name it in `available_tools`; if so, define only the `ToolDef`, not the executor.
- **Candidate-tree enrichment + overlay-disjointness (item 004):** the four arms share whatever
  `initial_state.files` the base task produces **today** (F1/F2 minimal, F3 broad — §B.3). Item 004
  enriches those trees identically across arms. 003 must not enrich; it must only guarantee the four
  arms share *whatever* the base tree currently is, byte-identical.
- **`f_ablation_spec` / `run-f-ablation` driver / seeded order (item 006).** No driver, no spec
  freeze, no execution.
- **No paid provider execution.** Offline construction + unit tests only.
- **No change to production `m1_spec`** F domain (still the 3 original, un-armed tasks).

## Constraints
- **TDD / FP house style** (CLAUDE.md): pure task-builder functions returning new immutable `Task`s;
  no shared mutable state. Mirror the existing `build_b_tasks` / `build_f_tasks` shape.
- **Frozen M1 specs must keep verifying** — arm-as-task is a *dataset/task-builder* change, not a
  `ConditionDef`/`ExperimentSpec` schema change. Run `verify_spec_hash` to confirm.
- **Backward compatible:** existing F runs / records / `report-m1` keep working; old `run_uid`s in
  committed JSONL still hydrate (the change is to the *write* side; readers key on the stored
  string).
- **Stage only own files — NO broad `git add`** (security lesson from item 002; an impl `git add -A`
  swept a secret). Impl/ship subagents stage explicitly.
- **Carry-forward watch (from 002-review):** item 003 introduces F task-arms with the 40-round
  ablation cap (frozen later in 006). Revisit whether per-task F `max_rounds` should route through
  `resolve_max_rounds` ([round_budget.py](../../../src/agent_eval_lab/runners/round_budget.py)) — the
  002 review flagged an F resolver-bypass. The 40-round *policy value* is frozen in 006's
  `f_ablation_spec`; 003 only needs the per-task override path to be reachable. Note it; full wiring
  may land in 006.
- No network. Offline TDD only.
