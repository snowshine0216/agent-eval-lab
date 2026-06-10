Verdict: PASS-WITH-NITS

Source: /ship steps 8+9
PR: https://github.com/snowshine0216/agent-eval-lab/pull/6

## Findings and resolutions

- BLOCKER (fixed pre-push): ws2-047 was passable by a no-op agent —
  final_state leg pre-satisfied by initial_state, trajectory leg purely
  negative (silent-failure hunter P0; adversarial P1, same evidence). Task
  fixed (positive `tool_call_match` leg requiring `search_docs`); a new
  conformance check grades EVERY task's verification against a synthetic
  no-op trajectory with the real graders and asserts fail — a zero-tool
  agent now scores 0/50 by construction. Red-phase: only ws2-047 failed.

- P1 (fixed pre-push): `_is_state_dependent` substring prompt matching
  ("T-1" in "T-10" = True) → word-boundary regex + negative pinning test.
- P1 (fixed pre-push): distractor conformance check (3) was a vacuous loop →
  real assertion (only NoToolCall may name a distractor).
- P1 (fixed pre-push): state-dependent layered_constraint tasks ws2-044 /
  ws2-049 invisible to the anti-rote proxy → pinned via explicit id set.

- NIT (by design, not changed): `exact_sequence` extra-call strictness on 7
  T1/T2 single-mutation tasks — over-calling is a graded failure mode (the
  exact v1 Qwen3-8B signal); multiset mode would not change extra-call
  behavior anyway.
- NIT (by design): `find_account` returns ToolSuccess with empty candidates
  (search semantics, documented + unit-tested); asymmetry with `get_account`
  ToolFailure noted for tool-description copy in a future item.
- NIT (recorded): adversarial solvability audit hand-traced the 6 hardest
  AllOf stacks (minted-id order, MaxToolCalls budgets, OnlyModifies leaf
  coverage, date-tie ambiguity) — all solvable, no ambiguous tasks found.
