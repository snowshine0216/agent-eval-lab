# Per-task `max_steps` ships as task data in item 002; runner wiring is item 004's contract

The v2 dataset's T3/T4 long-horizon tasks need a dependent tool chain of up to
~8 calls plus read/confirm turns — but the runner's loop budget today is a single
*global* `max_steps`, defaulting to `6` (`cli.py` `--max-steps`, consumed by
`runners/loop.py` as `for _ in range(max_steps)`). We decided item 002 ships the
per-task `metadata.max_steps` field and the data, defines its verify gate as
**parse + schema + conformance level (pure, no live model)**, and hands the runner
wiring (threading per-task `max_steps` through `multi_run.py`/`cli.py`) to item 004
as a **blocking contract**, not a nicety.

## Considered Options

- **Defer wiring to 004, ship data + field + conformance floor now** (chosen).
  Item 002 authors no live-run code it cannot exercise (AC13 forbids a live model
  run in 002), keeping TDD discipline intact. The conformance test asserts every
  T3/T4 task sets `max_steps >= dependent_calls + 2`, *proving the dataset is
  runnable once wired* without running it. Item 004 — which owns the live v2 runs
  and needs the wiring regardless — honors the floor.
- **Wire per-task `max_steps` through the runner in 002.** Rejected: 002 would
  ship runner changes with no live run to verify them (untestable code), pulling
  004's scope forward for no gain in 002's pure verify gate.
- **Raise the global default to cover the longest chain.** Rejected: a too-high
  global lets over-calling models wander, masking the `extra_call` signal on short
  tasks, and still mis-budgets the gradient between tiers — the per-task property
  is exactly what `max_steps` exists to express.

## Consequences

The division is hard to reverse cheaply because it creates a **silent failure
mode if 004 forgets the contract**: with the runner unchanged, every T3/T4 task
hits `stop_reason="max_steps"` and grades as a step-limit failure that *looks like
an agent failure but is harness starvation* — the precise "agent vs harness
failure" confound the dataset CI exists to prevent. The mitigation is structural:
the conformance floor lives in 002, and this ADR plus the spec's resolved-decisions
section hand 004 a blocking requirement to thread the per-task budget before any
live v2 run. Item 002's "end-to-end exercise" is therefore explicitly *deferred* —
its instrument is validated at parse/schema/conformance level, and live exercise
is 004's gate.
