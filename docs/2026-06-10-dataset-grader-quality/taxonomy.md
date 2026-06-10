# Workspace-world v2 — capability taxonomy

The v2 set (`workspace_tool_use_v2.jsonl`, 50 tasks) discriminates **between strong
models** by isolating six capabilities across four hardness tiers. Each task isolates
one capability (its failure attributes to one skill — the JD#4 taxonomy) and declares
one dominant difficulty knob.

## Capabilities × verification shape × knob

| capability | isolated skill | verification shape | dominant knob(s) |
|------------|----------------|--------------------|------------------|
| `tool_selection` | pick the right tool from a wide surface incl. overlapping distractors | `tool_call_match` | `distractor_count` |
| `argument_extraction` | extract literal/nested/enum/date args from NL | `tool_call_match` | `argument_complexity` |
| `multi_step_state` | execute a dependent chain; reach the target world-state | `final_state` (+`trajectory` if a policy clause) | `multi_step_depth` |
| `derived_reasoning` | reason over a tool *result* (filter/min/max/count) to compute an arg | `final_state` | `derived_argument` |
| `distractor_resistance` | avoid the plausible-wrong tool (`archive`/`find`/`draft`) | `all_of(final_state, trajectory:NoToolCall)` | `distractor_count` |
| `constraint_compliance` | honor a "but never / only / at most N" policy clause | `all_of(final_state, trajectory)` | `layered_constraint` |

## Tiers × expected-failure rationale

| tier | count | % | expected-failure rationale |
|------|-------|---|----------------------------|
| T1 sanity | 5 | 10% | Every frontier model passes — regression floor. If T1 fails, the harness or world regressed, not the model. |
| T2 moderate | 12 | 24% | Occasional `wrong_args` on nested/date/enum extraction and first-bite distractor pickups. The gradient that makes the boundary *visible*. |
| T3 hard | 22 | 44% | `extra_call` / `wrong_args` / `forbidden_action` from distractors and derived-argument reasoning. **Strong models are expected to sometimes fail here.** |
| T4 adversarial | 11 | 22% | Designed so **≥1 frontier model is expected to fail**: overlapping distractors + multi-clause policy + 4–8-step derived chains. |

T3 + T4 = 33 / 50 = **66%** (the "majority hard" directive).

## Difficulty knobs (closed vocabulary)

- `multi_step_depth` — a dependent chain of ≥4 calls; at least one call's args derive from a prior call's *result* (a minted id or a list/find-surfaced id).
- `derived_argument` — an argument the model must compute by reasoning over returned data (filter, min/max-by-date, count, cross-reference).
- `distractor_count` — a wide surface where ≥1 distractor (`archive_ticket`/`find_account`/`draft_email`) plausibly fits, forcing discrimination.
- `argument_complexity` — nested/enum/date/multi-field arguments extracted from NL.
- `layered_constraint` — a stated policy clause ("but never email", "only touch T-1", "at most 3 calls") encoded as `TrajectorySpec`.

Long-horizon is a *property* (chain depth via `multi_step_depth` + `max_steps`), not a
separate capability — making it a category would double-count the same skill.

## Determinism

Every world primitive is pure: ids mint via `max(...)+1`, no clock, no RNG, no I/O.
Dates are literal ISO strings; any date comparison a task requires is the *model's*
reasoning job, not the world's. A pure conformance suite
(`tests/datasets/test_workspace_tool_use_v2.py`) enforces every rule above mechanically.
