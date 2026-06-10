# Datasets

## `tool_use.jsonl` — tool-use eval tasks (slice 001)

Replaces the name-only `tool_selection.jsonl`. Each line is a full `Task` record
(see [`src/agent_eval_lab/tasks/codec.py`](../../src/agent_eval_lab/tasks/codec.py)
for the exact dict shape; load with `agent_eval_lab.tasks.loader.load_tasks`).

### Schema (per line)

- `id` — `tool-use-NNN`.
- `capability` — `tool_selection` | `argument_extraction`.
- `input.messages` — list of `MessageTurn` dicts (`{type:"message", role, content}`).
- `input.available_tools` — list of `{name, schema}`; `schema` mirrors the tool's
  entry in `tools/workspace_world.TOOL_SCHEMAS`.
- `verification` — a `tool_call_match` spec with `match` ∈
  {`exact_sequence`, `multiset`} and `expected_tool_calls` (no `call_id` — these
  are spec-time `ExpectedToolCall`s).
- `metadata` — `split` (`dev` | `held_out`), `version`, `provenance`,
  `world_template_id` (`workspace`), `difficulty_knob`
  (`baseline` | `distractor` | `enum_arg` | `multi_step`).
- `initial_state` — `{tickets, docs}` or `null`.

### Coverage

~20 tasks: tool-selection (distractor tools present), argument-extraction
(enum + exact-string args), and multi-step (create→update, exercising both
`exact_sequence` and `multiset` match modes). The world boundary and the AST
grader validate arguments with the **same** vendored JSON-Schema validator
(`tools/jsonschema_mini.py`), so "invalid" means the same thing in both — and a
schema-invalid argument is a `schema_violation`, never silently coerced to a pass.

## `recorded_runs.jsonl` — committed `RunResult`s for the baseline report

A small set of deterministic `RunResult` records (2 tasks × 2 runs) used as the
fixture for the baseline-report CLI smoke target:

```bash
uv run python -m agent_eval_lab.reports.baseline examples/datasets/recorded_runs.jsonl
```

This renders a deterministic baseline report (per-task `pass^k` reliability,
total/mean cost & latency, failure-category counts) without any network call or
API key — the records are pre-recorded, not produced live.
