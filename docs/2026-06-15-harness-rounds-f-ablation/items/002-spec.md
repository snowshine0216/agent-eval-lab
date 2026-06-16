# Item 002 — `max_rounds` plumbing + recorded policy fields

> Spec authored by **extraction** from the design doc (brainstorming/grill skipped per user
> override). Authoritative source: **Part A** (A.1/A.2/A.3) + **§9.2** + **§D.3** + **§11.2/§11.3** +
> **ADR-0017** of the design. Part G **step 2**. Also **absorbs item-001 carry-forwards** CF1/CF2/N3
> (see [001-review.md](001-review.md)).

## Goal

Give the agent loop a real, user-facing **turn budget** (`max_rounds`) per domain, record the
configured policy on every trajectory so any artifact proves whether it ran at 20 or 40, and split
resource-vs-time aggregation honestly. `safety_cap` is demoted to a backstop. The runner-level
`max_steps` *argument* is superseded (ADR-0017); the `metadata.max_steps` data field is untouched.

## Acceptance criteria

**Loop turn-bound (§A.1/A.2/A.3):**
- [ ] `run_single` (loop.py) gains `max_rounds: int | None` (default `None` ⇒ behavior unchanged).
  Checked at the **end** of each iteration (after the round's tool calls apply, so the turn's work
  is kept), beside the existing `safety_cap` check:
  ```python
  if max_rounds is not None and rounds >= max_rounds:
      stop_reason = "max_rounds"; max_rounds_bound = True; break
  ```
- [ ] New `stop_reason` literal **`"max_rounds"`** added to the `Trajectory.stop_reason` Literal
  (this also resolves item-001 **N3** — `_CAP_STOP_REASONS` already references it).
- [ ] Natural completion still breaks earlier (`completed_natural`), so a `max_rounds` stop means the
  model was **still editing** at the cap (uncommitted/incomplete) — assert this ordering in a test.

**Recorded policy on the trajectory (§9.2):**
- [ ] `Trajectory` gains three fields: `max_rounds: int | None`, `safety_cap: int | None`,
  `max_rounds_bound: bool` (default `False`).
- [ ] `serialize.py` **round-trips all three** with safe defaults for old records.
  **CF1 (from 001 review, P1):** there MUST be a round-trip test asserting `max_rounds_bound=True`
  (and the other two) survive `serialize → deserialize`. Without this, a genuinely max-rounds-capped
  run silently deserializes to the default `False` and is scored as a reliable pass^k pass — the exact
  latent bug item 001 flagged. This test is **mandatory**, not optional.

**CF2 (from 001 review, P1) — retire the defensive reads now that the field exists:**
- [ ] Replace `getattr(traj, "max_rounds_bound", False)` in **`metrics/reliability.py`** (`_run_passes`)
  and **`reports/classify.py`** (`_cap_bound`) with **direct attribute access** (`traj.max_rounds_bound`),
  now that `Trajectory` has the real field. A future field rename then becomes a loud `AttributeError`,
  not a silent `False`. Existing item-001 tests must stay green (the field now always present, default
  `False`).

**Per-domain config + granularity (§A.2 / §11.3 / ADR-0017):**
- [ ] Per-domain default `max_rounds = {"F": 20, "D": 50}` on the experiment spec, with an optional
  per-task `metadata.max_rounds` override. **Resolution: task override > domain default.**
- [ ] `safety_cap` stays a higher backstop (code **200** / browser **~300**).
- [ ] Threaded into `make_f_run_fn` and `dset_run`. **B is config-only/deferred** (no live B runner — §9.9).
- [ ] The runner-level `max_steps` **argument** is superseded (ADR-0017); the `metadata.max_steps`
  **data field** is left untouched.

**Aggregation split (§D.3):**
- [ ] **Resource use (tokens, cost):** summed/aggregated over **all valid runs incl. capped** (spent
  even on capped runs).
- [ ] **Time-to-natural-completion (rounds, wall-time):** right-censored on capped runs →
  survival-style / lower-bound (`≥X`) over uncensored, with the censoring count disclosed.
- [ ] `n_censored` (aggregate.py) now **includes `max_rounds_bound`** (currently only `safety_cap_bound`).

## Non-goals
- **No ablation, no arm-as-task, no Factor P/V** (items 003–006). No new domains beyond F+D config.
- **B live runner** — config-only/deferred (§9.9). Do not build a B loop.
- **No change to pass^k censor predicate** — item 001 already enforces it; this item only makes the
  `max_rounds_bound` producer real and swaps the defensive read for a direct one (CF2).
- **No change to `metadata.max_steps` data field** or the classifier's `step_exhaustion` row.

## Constraints
- **TDD / FP house style** (CLAUDE.md): pure functions, immutability; `run_single` stays a function
  of its inputs. Use a **stub loop** for TDD of the bound (no provider calls — §G2 "TDD with a stub loop").
- **Backward compatible:** old records (no `max_rounds`/`safety_cap`/`max_rounds_bound` keys)
  deserialize with defaults and classify/score exactly as before.
- **ADR-0017** is the governing decision (loop budget = safety_cap backstop + max_rounds; runner
  `max_steps` superseded) — already written; this item implements it. Amend it only if implementation
  reveals a gap.
- **Frozen M1 specs must keep verifying** — adding fields to `Trajectory`/serialize is record-level,
  not `ConditionDef`/`ExperimentSpec` schema; confirm `verify_spec_hash` still passes.
- No network. Offline TDD only.
