Verdict: PASS

Subagent: sonnet / Source: claude/dataset-grader-quality-002 / Entry point exercised: loader · conformance suite · e2e MockTransport dry run · full gates

## Observed behavior per criterion

**AC1 — Tool surface (8 tools, 3 distractors).** Spec headline says "8" but the body enumerates 3 v1 tools + 3 §5 primaries + 3 distractors = 9 total — the headline is a spec typo. Implementation ships 9 tools in `WORKSPACE_TOOLS`: `search_docs`, `create_ticket`, `update_ticket`, `get_account`, `list_tickets`, `send_email`, `archive_ticket`, `find_account`, `draft_email`. Three distractors confirmed present. No conformance test asserts exactly 8 (none was written), so the implementation is internally consistent with the spec body. Finding: spec-headline typo (9 not 8), implementation correct, no test failure.

**AC2 — World state `{tickets, docs, accounts, emails}`.** `workspace.py` confirms all four roots. `_send_email`/`_draft_email` append to `emails`; `_get_account`/`_find_account`/`_list_tickets` return `state` unchanged. Ticket gains `assignee` and `created` fields (checked in v2 tasks). `_next_email_id` mirrors `_next_ticket_id`. Verified by reading `workspace.py` + e2e exercise (email `e-1` minted correctly).

**AC3 — `list_tickets` enables derived-reasoning tasks.** `_list_tickets` returns `{ticket_ids, tickets}` with all fields; filter semantics pure: unknown value → empty result, no error. Verified in `workspace.py` lines 198–212 + 23 tasks using `multi_step_depth`/`derived_argument` knobs confirmed by loader script.

**AC4 — 50 tasks, version "2", tier mix, metadata fields.** Loader: `load_tasks(Path("examples/datasets/workspace_tool_use_v2.jsonl"))` → 50 tasks. IDs: sorted match `ws2-001`…`ws2-050` exactly (no missing, no extra). All 50 have `version="2"`, `provenance="hand_written"`, `world_template_id="workspace-v2"`, `split="dev"`. Tier mix (id ranges): T1=5, T2=12, T3=22, T4=11 (T3+T4=33/50=66%). `test_tier_mix_matches_allocation` passes.

**AC5 — Six capabilities, all present, no stray labels.** Capability histogram: `argument_extraction=8, constraint_compliance=6, derived_reasoning=11, distractor_resistance=5, multi_step_state=12, tool_selection=8`. Set equals the exact six specified. `test_all_six_capabilities_present_and_no_stray_labels` passes.

**AC6 — Verification shape matches tier/capability.** Histogram: `tool_call_match=16, final_state=23, all_of=11`; `final_state`+`all_of`=34 ≥ 33 (T3+T4 count). No `LlmJudgeSpec` or `OutputMatchSpec` present. `test_verification_histogram_dominated_by_state_and_all_of` passes.

**AC7 — Long-horizon depth real and bounded.** 23 tasks with `difficulty_knob` in `{multi_step_depth, derived_argument}` ≥ 15 required. State-dependency proxy (`_is_state_dependent`) enforces the anti-rote-chain property. `test_state_dependency_proxy_for_derived_tasks` + three proxy unit tests all pass.

**AC8 — `max_steps` per-task data, T3/T4 floor.** `TaskMetadata.max_steps: int | None = None` confirmed in `schema.py`. All 33 T3/T4 tasks set `max_steps`; `test_max_steps_floor_for_hard_tiers` passes (floor ≥ 4, and ≥ dependent_calls + 2 for tasks with `ExpectedToolCalls`). Runner wiring deferred to item 004 per ADR-0004.

**AC9 — Taxonomy doc and rubric doc exist and self-consistent.** `docs/2026-06-10-dataset-grader-quality/taxonomy.md` present: six capabilities × four tiers grid; expected-failure rationale per tier; tier-count table matches AC4 exactly (T1=5/10%, T2=12/24%, T3=22/44%, T4=11/22%); knob vocabulary. `docs/2026-06-10-dataset-grader-quality/rubric.md` present: version string `rubric-v1`; checklist items (a)–(g) complete; re-review policy stated.

**AC10 — Per-task review evidence recorded.** All 50 tasks have `metadata.review = "passed:rubric-v1"`. `review-ledger.md` has exactly one entry per task id (ids `ws2-001`…`ws2-050`). `test_every_task_has_review_field` and `test_review_ledger_has_one_entry_per_task` pass.

**AC11 — Determinism enforced.** All 9 tools run with fixed `(args, state)` twice → identical `(state', outcome)`. No clock, RNG, network, or filesystem call in any `workspace.py` impl function. Property confirmed by manual double-invocation test.

**AC12 — Dataset CI.** `uv run pytest tests/datasets/ -q` → 22 passed (3 v1 + 19 v2). Conformance module checks: parse, registered tools, schema-valid expected calls, state-path roots, preconditions, tier mix, capability set, verification histogram, distractor-never-expected, no-op pre-satisfaction (every task fails a zero-tool agent), state-dependency proxy, review coverage, ledger parity, max_steps floor.

**AC13 — Full gates green, v1 untouched.** `uv run pytest` → 227 passed. `uv run ruff check .` → All checks passed. `uv run ruff format --check .` → 64 files already formatted. No live model run performed. `TaskMetadata.max_steps` and `.review` are optional/defaulted — v1 tasks unaffected.

## E2e dry run results (entry point: `run_task_k` with `httpx.MockTransport`)

- **ws2-001 (T1, `tool_call_match`)** — MockTransport plays `search_docs(query="refund policy")` → confirmation. `run_task_k` → `grade.passed=True`. Asserted.
- **ws2-040 (T4, `all_of`)** — Optimal path: MockTransport plays `send_email(to="ada@example.com", ...)` (not `draft_email`) → confirmation. `run_task_k` → `grade.passed=True`. Both `final_state` sub-result (`emails.e-1.state=sent`) and `trajectory_policy` sub-result (`NoToolCall(draft_email)=True`) confirmed in evidence dict.
- **ws2-040 (T4) no-op path** — MockTransport plays `draft_email(...)` instead. `run_task_k` → `grade.passed=False`. `final_state` fails (`emails.e-1.state="draft" ≠ "sent"`); `trajectory_policy` fails (`forbidden_action: draft_email`). Asserted.

## Failures

None. The spec headline "exactly 8 tools" is a typo (body enumerates 9 = 3+3+3); the implementation and all tests are consistent with 9 tools. No AC test asserts the headline number, so no test failure occurs. Noted as a spec-typo finding only.
