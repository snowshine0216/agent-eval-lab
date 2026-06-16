# The loop budget is `safety_cap` (tool calls) + `max_rounds` (turns); runner-level `max_steps` is superseded

ADR-0004 described the runner loop as `for _ in range(max_steps)` — a single
*turn* budget — and chose a *per-task* `metadata.max_steps` over a global one. The
live `runners/loop.py` has since moved to `while True` bounded by **`safety_cap`**
(total tool calls, D35) and emits `stop_reason="safety_cap"`, never `max_steps`;
the runner-level `max_steps` argument is dormant/compatibility-only. This work adds
**`max_rounds`** — a cap on the recorded `rounds` (model turns) — as the
user-facing turn budget, with `safety_cap` demoted to a higher backstop. We name
it `max_rounds` (matching the `rounds` field, not the overloaded "steps") and
**supersede the runner-level `max_steps`**.

## Decision

The loop has two orthogonal budgets: `safety_cap` (tool calls; backstop) and
`max_rounds` (model turns; the user-facing bound, `stop_reason="max_rounds"`,
`max_rounds_bound` on the trajectory). `max_rounds` resolves **per-task
(`metadata.max_rounds`) over a per-domain experiment-spec default** (`{F:20,
D:50}`); the F-ablation pins `{F:40}` at the experiment level. The per-task data
field **`metadata.max_steps` is untouched** — only the *runner-level* `max_steps`
argument is superseded.

## Considered Options

- **`max_rounds` capping `rounds`** (chosen). Matches the live record field;
  avoids reviving "steps", which is overloaded (`step_limit_exceeded`/
  `MaxToolCalls` count tool *calls*, a different axis).
- **Reuse the name `max_steps` for the live turn bound** (rejected). Doubles down
  on an overloaded term and mismatches the `rounds` field the record already uses.
- **Per-domain default + per-task override** (chosen). Honors the operator's
  per-domain ask (code 20 / browser 50) while keeping ADR-0004's per-task escape
  hatch via `metadata.max_rounds`; the ablation expresses one uniform budget as a
  single frozen spec value.
- **Pure per-task budgets** (ADR-0004's original; partially retained). Still
  available via the override, but no longer the *default* — agentic-v1's few,
  homogeneous tasks per domain make a per-domain default the simpler primary.
- **Pure global budget** (rejected, as in ADR-0004 — masks the `extra_call`
  signal on short tasks).

## Consequences

- **Partially supersedes ADR-0004**: the runner-level `max_steps` loop argument is
  retired; the `metadata.max_steps` task-hint data field is not.
- `stop_reason="max_rounds"` and `max_rounds_bound` join `safety_cap`'s
  censoring semantics (success-metric failure; time-to-completion right-censored;
  tokens/cost observed) — the classifier's budget-exhaustion override fires on
  `max_steps` (legacy records) + `safety_cap` + `max_rounds`.
- A future reader seeing three budget-ish names (`max_steps` dormant,
  `safety_cap`, `max_rounds`) has this record explaining which is live and why.
