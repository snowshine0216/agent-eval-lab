Verdict: PASS

Subagent: sonnet
Plan checklist items: 7 (Tasks 1–7)
Verified present in diff: 7 / 7

---

## Per-task checklist

| Task | Plan item | Status |
|------|-----------|--------|
| 1 | Pure `ablation_run_order` (`ablation_order.py` + 6 tests) | OK |
| 2 | Frozen `f_ablation_spec` (`f_ablation_spec.py` + 5 tests) | OK — with faithful deviation (see below) |
| 3 | Public `grade_f_attempt` wrapper in `f_candidate.py` + test | OK |
| 4 | `_run_f_ablation_command` driver + 3 tests | OK — with faithful deviation (see below) |
| 5 | CLI subparser + dispatch wiring + 2 wiring tests | OK |
| 6 | Report-compat confirmation test (no source change) | OK |
| 7 | `ruff check . && ruff format --check .` gate (commit `da5c966`) | OK |

---

## Drift findings

### Deviation 1 (Task 2) — `test_policy_records_40_rounds_12_arms_and_seed` store-absence split (faithful intent)

**Plan:** one combined test calls `build_f_task_arms(evaluator_store=Path("/nonexistent"))` inline to cross-check the 12 task-arm ids against the dataset builder.

**Actual:** split into two tests:
- `test_policy_records_40_rounds_12_arms_and_seed` — pure math check (`f-{base}-{arm}` set construction, no store); always runs.
- `test_policy_task_arm_ids_match_dataset_builder` — calls `build_f_task_arms` with the real store; decorated `@requires_store`, skips in CI where the golden store is absent.

`tests/experiments/test_f_ablation_spec.py` lines 863–869.

Assessment: **faithful intent**. The plan's single test would have raised `FileNotFoundError` (or a similar I/O error) in CI where the store is absent, which would be a spurious failure, not a genuine spec miss. The split preserves the spec intent (12-arm coverage asserted in both paths) while making CI green. No logic lost.

### Deviation 2 (Task 4) — driver skips `load_evaluator_config` when a factory is injected (faithful intent)

**Plan:** driver always calls `load_evaluator_config(args.evaluator_config)` then branches on factory injection (`factory = run_fn_factory or _default_run_fn_factory(...)`).

**Actual:** driver branches on `run_fn_factory is not None` first:
- Injected factory path: uses `Path("/nonexistent")` as store sentinel, skips `load_evaluator_config` entirely.
- Real path: calls `load_evaluator_config` then `_default_run_fn_factory`.

`src/agent_eval_lab/cli.py` lines 150–164 (in `_run_f_ablation_command`).

Assessment: **faithful intent**. The plan's approach would have called `load_evaluator_config` on a nonexistent path in every test, requiring either a real config file or additional monkeypatching. The actual implementation is strictly cleaner: tests never touch I/O that doesn't belong to them, and `load_evaluator_config` (a real file read) stays on the real user path only. No semantic difference for production invocations.

---

## Critical scope confirmations

**NO paid-execution path in tests or on import:**
- `_default_run_fn_factory` is the ONLY function that constructs an `httpx.Client` and calls `make_f_run_fn`; it is reached exclusively when `run_fn_factory is None` (real user invocation, non-`--dry-run`).
- Every driver test in `tests/cli/test_run_f_ablation.py` injects `_make_recording_factory(calls)` via the `run_fn_factory` keyword arg. No test calls `_default_run_fn_factory` or constructs any network client.
- `test_dry_run_writes_order_and_makes_zero_run_fn_calls` asserts `calls == []` — the dry path makes zero `run_fn` calls.
- Importing `cli.py` or `f_ablation_spec.py` does NOT trigger any network call; all provider-level objects are built lazily inside `_default_run_fn_factory`.

**Frozen M1 intact:**
- No field added to `ConditionDef`, `ExperimentSpec`, or any shared schema dataclass.
- `AblationPolicy` is a brand-new separate dataclass in `f_ablation_spec.py`; it is not an `ExperimentSpec` field.
- `condition_id` stays `provider:model` throughout.
- `test_building_the_ablation_spec_does_not_touch_m1` explicitly freezes M1 spec and asserts `verify_spec_hash(m1)` still passes after building/freezing the ablation spec.
- The committed `reports/agentic-v1/M1-spec.frozen.json` is not in the diff.

**No stray user files:**
- Diff contains exactly 10 files: `PROGRESS.md` (chore, incidental), `cli.py`, `ablation_order.py`, `f_ablation_spec.py`, `f_candidate.py`, `tests/cli/__init__.py`, `tests/cli/test_run_f_ablation.py`, `tests/experiments/test_ablation_order.py`, `tests/experiments/test_f_ablation_spec.py`, `tests/runners/test_f_candidate.py`.
- No `reports/validation.py`, `tests/reports/test_validation.py`, `CONTEXT.md`, `m1-report-enhancement-design.md`, `evaluator-only/`, or `.env*` files present.
