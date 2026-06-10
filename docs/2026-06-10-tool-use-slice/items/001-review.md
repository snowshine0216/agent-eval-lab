Verdict: PASS-WITH-NITS
Source: /ship steps 8+9 (pre-landing parallel review: pr-review-toolkit:code-reviewer + silent-failure-hunter; adversarial review: general-purpose)

Two real latent bugs in shipped grader behavior were found and **fixed pre-PR**
(triage round 1, commits `56399c8`, `ab5d9c8`); the remaining flagged items are
nits or documented follow-ups (no shipped-behavior false-pass). Suite green at 88
tests after fixes.

## Findings — fixed (were latent bugs)

- **`graders/exact_match.py:22` — output mismatch mislabeled `wrong_tool`** (code-reviewer P0).
  The OutputMatchSpec scorer tagged a text mismatch with a tool-call failure
  category, which would pollute `failure_counts` on any mixed dataset. Fixed:
  `failure_reason` now defaults `None` (output mismatch is not in the tool-call
  `FailureCategory` taxonomy); test updated. Commit `56399c8`.
- **`graders/ast_tool_match.py` `_grade_exact_sequence` — same-tool swapped-args mislabeled `wrong_args`** (adversarial P1).
  `order_mismatch` was only detected when tool *names* differed; a reordering of
  the same tool with swapped args reported `wrong_args`. Fixed: added a
  full-`(name, canonical-args)`-multiset check (exact-equal → pass; multiset-equal
  but order differs → `order_mismatch`; else per-position diagnosis). New test
  `test_order_mismatch_same_tool_swapped_args`. Commit `ab5d9c8`.

## Findings — dismissed (verified not bugs)

- **Empty observed + empty expected → PASS** (silent-failure-hunter P0). This is
  *correct*: an empty `expected_tool_calls` is a valid "no tool should be called"
  assertion, so empty-vs-empty is a true pass and empty-vs-nonempty is `extra_call`.
  Distinguishing "model correctly made zero calls" from "runner produced no
  trajectory due to error" is the runner's job (termination_reason), not the
  grader's. No change.
- **`FakeModel` `call_id` always `-0`** (code-reviewer P0). Each script step emits
  exactly one tool call, so `call_id=f"{task_id}-{step}-0"` is unique per step and
  round-trips fine — not a collision. The misleading docstring ("…, index") was
  corrected to "(task_id, step)" (commit `ab5d9c8`). No correctness change.

## Findings — documented follow-ups (nits; not shipped-behavior bugs)

- **`runners/provider.py` `_parse_arguments` `{"__raw__": raw}` fallback** masks an
  unparseable-JSON arguments string (silent-failure-hunter P0). In *this* slice the
  provider makes **zero live calls** (no keys; FakeModel only) and every
  workspace-world schema sets `additionalProperties: false`, so this fallback
  fails-closed as `schema_violation` (a correct FAIL, never a false pass). The
  design's intent (unparseable args → `malformed_call`) is a clean refinement best
  made when the live provider path is first exercised. **Follow-up: address before
  the Weeks 7–8 live model comparison.**
- **`tasks/codec.py` unknown `type` tag → bare `KeyError`** (P1): a corrupted JSONL
  record raises an opaque `KeyError` rather than a typed deserialization error.
  Loud failure, just unclear message. Round-trip is correct for valid data. Nit.
- **`provider.py:67` `content or ""`** and **`codec.py` `.get("arguments", {})`** (P1/Notes):
  benign defaulting; acceptable for v0, no false-pass. Nit.
- **Orphaned `ToolCallTurn` before the `max_tool_calls` check** (adversarial P2):
  trajectory carries an unpaired tool-call turn on a limit hit; the grade is still
  correctly `step_limit_exceeded`. Cosmetic structural nit.

## Acceptance / quality summary
- 88 tests pass; `ruff check` + `ruff format --check` clean.
- Purity confirmed by reviewers: graders/metrics/report renderer are I/O-free;
  I/O isolated to `loader.py` + `reports/baseline.py:main`.
- Schema-first integrity confirmed: `bool` excluded from `integer`/`number`; no
  silent type coercion or arg repair in the world boundary or grader.
- Determinism confirmed: `trajectory_hash` uses `json.dumps(sort_keys=True)` over
  stable codec output; `canonicalize` sorts; `pass^k` handles zero/variable k.
