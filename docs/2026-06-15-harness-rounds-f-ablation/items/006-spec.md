# Item 006 — `run-f-ablation` driver + freeze `f_ablation_spec` (code only)

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override). Authoritative source: **§B.6** (roster/size), **§B.7** (`ablation_run_order` pure fn +
> driver + realized-order sidecar), **§11.9**, **§G6**, **Part G step 6**. Orchestrates items 003
> (12 task-arms), 004 (enriched trees), 005 (Factor V sandbox executor) into the seeded run order.
> **CODE ONLY — NO pilot, NO full run, NO provider calls.**

## Goal

Build the orchestration the ablation needs: a **seeded, block-randomized execution order** and a
**`run-f-ablation` CLI driver** that runs attempts in that order across (model × task-arm × rep),
plus a **frozen `experiments/f_ablation_spec.py`** recording the 40-round F policy, the 12 task-arms,
the 4-model roster, and the seed. Today both run paths are strictly per-condition-sequential
([_run_f_command](../../../src/agent_eval_lab/cli.py:870), `run_f_candidate`) and nothing consumes a
global order — so provider drift / time effects could masquerade as a P/V effect (§B.7). This item
adds the net-new orchestration so a P/V "win" can't be confounded with API-call timing. **It stops
before any paid execution** — the user triggers the pilot + full 240-attempt run later.

## Acceptance criteria

**Pure `ablation_run_order` (§B.7 / §11.9):**
- [ ] A pure function `ablation_run_order(seed, models, base_tasks, k)` (no I/O, deterministic)
  returning the execution order as a sequence of `(model/condition, task_arm_id, repetition)` units.
- [ ] It **interleaves all four arms within each `(model, base-task, repetition)` block** — so within a
  block the bare/prompt/feedback/both attempts are shuffled together (not arm-grouped), so provider
  drift across the block can't align with one arm (§B.7).
- [ ] **Deterministic**: same `seed` ⇒ identical order (no `random` without a seeded RNG, no wall-clock).
  Different seeds ⇒ different orders.
- [ ] **Total coverage, no dup**: the order contains exactly each `(model × 12 task-arm × k)` unit once
  (4 arms × 4 models × 3 base tasks × k=5 = **240** units at k=5). Unit-tested for coverage +
  no-collision + seed-reproducibility + interleaving.

**`run-f-ablation` CLI driver (§B.7 / §G6):**
- [ ] New CLI subcommand `run-f-ablation` that executes attempts in the **frozen** `ablation_run_order`
  across all (model × task-arm × rep) — the **arm is encoded in each run's `task_id`** (§B.2, from
  003) — using `build_f_task_arms` (003), `build_candidate_tree` (enriched, 004), and `make_f_run_fn`
  (V routing, 005).
- [ ] Writes **one artifact per condition** (`runs-ablation-{slug}-F.jsonl`, **all 12 task-arms
  inside**) — not per-arm files (§B.2 retires per-arm filenames).
- [ ] Writes a **realized-order sidecar** recording the realized execution / API-call order for audit
  (the API-call order is what controls drift, not the on-disk record order — §10.7).
- [ ] **No paid execution in this item**: the driver makes provider calls only when the **user**
  invokes it. Tests exercise it with an **injected fake run_fn** (no network); optionally a
  `--dry-run` that prints/writes the realized order without provider calls. CI/this item must not
  trigger a paid run.

**Frozen `experiments/f_ablation_spec.py` (§B.1 / §B.6 / §11.9):**
- [ ] A **separate** `f_ablation_spec` (distinct from production `m1_spec`) recording: the **40-round**
  uniform F policy (production F stays 20), the **12 task-arms**, the **4-model roster**
  (deepseek-v4-pro, GLM-5.1, MiniMax-M3, Qwen3.6-35B — §B.6), and the **seed** for `ablation_run_order`.
- [ ] The spec is **frozen** (spec_hash via the existing `freeze_spec` path, or an equivalent recorded
  hash) so the 40-round treatment + order are auditable (§9.2).
- [ ] **Does NOT touch the committed frozen M1 specs** — `verify_spec_hash` for M1 still passes; no
  `ConditionDef`/`ExperimentSpec` schema change (arm rides `task_id`; `condition_id` stays
  `provider:model` so pricing resolves).

**Report compatibility (§B.2):**
- [ ] Confirm (do not change) that `report-m1`'s `_load_run_results` groups by `task_id`, so per-arm
  `pass^k` (4 sets of 3 tasks) falls out of the one-artifact-per-condition output with no report-side
  plumbing.

## Non-goals (deferred → SKIPPED.md / out of run scope)
- **The pilot (≈24) + the full 240-attempt paid run** (Part G step 6 *execution*) — real, irreversible
  API spend; user-triggered later via this driver.
- **The descriptive report** (Part C narrative + §D.2/§D.3/§D.4) — Part G **step 7**, needs run results.
- **Held-out F4–F6 confirmation** (Part F) — separate follow-up phase.
- No new domains; no B live runner; no `arm_id`/`ConditionDef`/`ExperimentSpec` schema change.

## Constraints
- **No paid execution / no network in tests or CI.** The driver's provider calls happen only on a user
  invocation. Every test injects a fake `run_fn` / fake executor. This is the run's hard scope boundary
  (MASTER-SPEC: "stop before any paid provider execution").
- **Pure order fn**: deterministic, seeded RNG only (no wall-clock, no unseeded `random`). FP house
  style: the order is a pure function of `(seed, models, base_tasks, k)`.
- **macOS-local V**: when the user runs the driver, V arms route through the 005 sandbox on macOS and
  skip/guard off-macOS (already handled in `make_f_run_fn`). The driver does not re-implement that.
- **Frozen M1 specs keep verifying** — the new spec is additive; confirm `verify_spec_hash` for M1.
- **Stage only own files — NO broad `git add`** (security lesson, item 002).
- CI runs `ruff check .` AND `ruff format --check .` whole-repo; pytest with `-o addopts=""`.
- **Roster note:** §B.6 names Qwen3.6-35B; m1_spec lists it as a PROVISIONAL siliconflow id. The
  ablation spec records the roster as the design names it (provisional ids labelled); actually running
  unreachable models is the user's later concern (deferred execution), not this item.
