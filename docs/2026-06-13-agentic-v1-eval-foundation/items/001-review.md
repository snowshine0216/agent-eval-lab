# Item 001 Code Review — Records + Runner Revision

**Branch:** `feat/agentic-v1-001-records-runner` vs `autodev/agentic-v1-eval-foundation`  
**Reviewer:** Claude Code (HIGH effort)  
**Date:** 2026-06-13  
**Test suite:** 697 passed (full suite green); ruff clean on all changed files.

---

## VERDICT: PASS-WITH-NITS

Zero blocker bugs. Zero latent correctness bugs. One latent type-annotation bug. Four style nits.

---

## Findings by Severity

### Blocker Bugs

None.

### Latent Bugs

**L1 — `multi_run.py:34` — Wrong return-type annotation on `_grade_one`**

```python
def _grade_one(*, task, registry, trajectory) -> RunResult:   # ← wrong
    ...
    grade = grade_trajectory(...)  # returns GradeResult
    return grade
```

`grade_trajectory` (in `graders/dispatch.py:58`) returns `GradeResult`, not `RunResult`. The annotation says `-> RunResult` but the function returns a `GradeResult`. The caller `_run_one` correctly uses it as a `GradeResult` (passes it to `RunResult(... grade=grade ...)`), so there is zero runtime impact and all tests pass. However, the wrong annotation will mislead a static type-checker (mypy would flag a type error on the call site in `_run_one`) and any future programmer reading the signature.

**Fix:** Change `-> RunResult:` to `-> GradeResult:` at line 34 and add `GradeResult` to the import from `agent_eval_lab.records.grade` (it is already imported for other uses).

---

### Nits

**N1 — `tests/runners/test_loop_effects.py:210, :254` — Irregular indentation**

Two occurrences where `temperature=0.0,` is indented with 16 spaces instead of 12, left over from removing `max_steps=4,` above it. Python accepts it (it is inside a call expression) and ruff passes, but it is inconsistent with all surrounding call sites.

**Fix:** Align `temperature=0.0,` to 12-space indent (matching the surrounding kwargs) at both lines.

---

**N2 — `tests/reports/test_classify.py` — Stale test names**

Two test names are now misleading:
- `test_classifier_version_is_fc_v2` (line ~928) now asserts `CLASSIFIER_VERSION == "fc-v3"`. The docstring was updated with a redirect note, which partially mitigates this, but the function name is wrong.
- `test_subcategory_vocabulary_is_closed_at_16_after_fc_v2` (line ~936) is now `pass` (a no-op stub). The invariant it guarded (closed vocabulary) is now guarded by `test_subcategory_vocabulary_is_closed_at_19_after_fc_v3`, so nothing is lost, but a dead test body named for a constraint it no longer asserts can confuse future maintainers.

**Fix:** Rename `test_classifier_version_is_fc_v2` → `test_classifier_version_is_fc_v3`; delete the now-empty `test_subcategory_vocabulary_is_closed_at_16_after_fc_v2` stub (its invariant is fully covered by the v3 test).

---

**N3 — `classify.py:159–184` — `pre_probe_failed` subcategory is only reachable when both probes are unhealthy**

The loop sets `stop_reason="env_unhealthy"` only when `post_health.post_healthy is False`. The classifier's `_classify_environment` checks `pre_healthy` first, which means `pre_probe_failed` fires only when `pre_healthy=False AND post_healthy=False`. A run where the pre-probe is unhealthy but the post-probe is healthy will get `stop_reason="completed_natural"` and never trigger `_classify_environment` at all.

This is **faithful to the spec** ("if the post probe is unhealthy set `stop_reason=env_unhealthy`") and is not a code bug. Worth documenting explicitly so future maintainers do not expect `pre_probe_failed` to fire when the pre-probe alone is unhealthy.

**Suggestion:** Add a brief comment in `_classify_environment` noting that `pre_probe_failed` requires the run to have been stopped as `env_unhealthy`, which means the post-probe was also unhealthy.

---

**N4 — `multi_run.py:133` — `_grade_one` has an unannotated `trajectory` parameter**

```python
def _grade_one(*, task: Task, registry: Mapping[str, ToolDef], trajectory) -> RunResult:
```

`trajectory` lacks a type annotation. It should be `trajectory: Trajectory`.

---

## Instrument-Correctness Checklist

### 1. Censoring loop (`loop.py`)

- **200-tool-call cap counting:** Cumulative tool calls are counted across all turns using `sum(tool_call_counts.values())`. The check fires after each turn's full set of tool calls is processed. Boundary: `>= 200` is correct (not `>`); at exactly 200 the run stops. A single turn with many tool calls may overshoot the cap by one turn's worth, which is intentional ("generous" cap per §18.1). No off-by-one bug.
- **`completed_natural` / `safety_cap` / `env_unhealthy` / `parse_failure` precedence:** Exactly per spec. `parse_failure` sets `stop_reason="parse_failure"` and breaks; post-probe then runs and records `env_health`, but `stop_reason` stays `parse_failure` because the upgrade condition `stop_reason in ("completed_natural", "safety_cap")` excludes it. `env_unhealthy` only overrides `completed_natural` or `safety_cap`, not parse failures. Correct.
- **ADR-0008 effect-request fulfillment:** Unchanged. The `_fulfill` call and `ExecutionRequest` dispatch are byte-identical to the pre-revision runner.
- **Parse-failure handling:** Unchanged byte-for-byte.

### 2. Replacement-trial VOID (`multi_run.run_task_k_valid`)

- **VOID predicate:** `invalid_count / (invalid_count + k_valid) > max_invalid_rate`. This is the minimum achievable final invalid-rate (best case = all remaining trials valid, so the final denominator is `invalid_count + k_valid`). Correct per D28/D34. The `test_run_task_k_valid_no_void_when_best_case_under_threshold` test specifically validates the boundary against a naive `(invalid + remaining_needed)` denominator and confirms the correct formula.
- **Never scores over < k_valid valid runs:** VOID returns early before the `while` loop exits; the non-VOID return path only runs when `len(valid_runs) >= k_valid`. Correct.
- **`attempt_index` monotone:** Incremented by 1 after every trial, valid or invalid. Never reset. Correct.
- **Back-compat `run_task_k` path:** `run_task_k` accepts `max_steps` for CLI compatibility (kept in signature, not forwarded to `run_single`), threads `run_uid` per run index, passes `health_probe_fn=None`. Grading is byte-identical to the pre-revision path (verified by `test_run_task_k_defaults_yield_byte_identical_workspace_run`).
- **Division-by-zero guard:** If `k_valid=0`, the while-loop condition `len(valid_runs) < 0` is immediately `False`, so the VOID check (which would divide by `0 + 0`) is never reached. Edge case is benign.

### 3. v1 back-compat (`trajectory.py` + `serialize.py`)

- **Loading v1 artifacts:** `trajectory_from_dict` checks `"schema_version" not in data` as the routing gate. V1 artifacts on disk have no `schema_version` key. The parsed `turns`, `usage`, and `parse_failure` are constructed first, then passed to `Trajectory.v1_compat` which applies safe defaults for all new fields and tags `schema_version="1"`. No pre-revision artifact can fail to load.
- **`trajectory_to_dict` always emits `schema_version="2"` and all new keys:** Confirmed. The dict literal always includes `schema_version`, `rounds`, `wall_time_s`, `tool_call_counts`, `safety_cap_bound`, `env_health`, and `run_uid`. `max_tokens` is still conditionally emitted (`if trajectory.max_tokens is not None`), matching the prior on-disk shape for artifacts without it. Correct.
- **`test_committed_runs.py` and `test_golden_conformance.py`:** Both pass (v1 committed artifacts load via v1_compat; golden cases graded identically).

### 4. fc-v3 classifier (`classify.py`)

- **`environment_failure` ordering:** Checked at step 4 of `classify_run`, after `passed` (row 1), after the `parse_failure is None` guard (row 2), after `_classify_parse_failure` (rows 3), and before `first_execution_evidence` / `_classify_execution_evidence` (rows 4-9). Matches the spec: "after parse/harness, before execution grading."
- **Pure/total/versioned:** `_classify_environment` returns `None` for all non-`env_unhealthy` runs, leaving the fc-v2 chain unchanged. The function never raises. Versioned as `fc-v3`. All pre-existing fc-v2 category/subcategory verdicts are identical (only the version label changed).
- **Hypothesis totality test:** `test_classify_run_is_total_and_closed` covers all six stop_reasons including `env_unhealthy`. Passes.

### 5. Cost stays derived

No pricing import in any records or runner file. Confirmed by grep.

### 6. Silent failures / swallowed exceptions

None found. Exceptions from `apply_fn`, `executor`, `chat_completion`, and `health_probe_fn` propagate up normally. No bare `except` clauses in changed code.

### 7. Frozen/shared structure mutation

`tool_call_counts` is passed from the loop's mutable local dict into the frozen `Trajectory`. After construction, the function returns and the dict is no longer accessible from the loop's scope. The `default_factory=dict` on `Trajectory.tool_call_counts` correctly avoids the mutable class-level default antipattern. `env_health_to_dict` copies all fields; `trajectory_to_dict` copies `tool_call_counts` via `dict(...)`. No shared-mutable-state bug.

---

## Summary

The implementation is correct across all scrutinized dimensions. The measuring instrument is sound: the safety cap counts correctly, the VOID predicate uses the right denominator, v1 artifacts load faithfully, parse failures are not overridden by the post-probe, and fc-v3's `environment_failure` is inserted at the correct priority. The one latent type annotation bug (`_grade_one -> RunResult` should be `-> GradeResult`) has zero runtime impact. Style nits are minor and do not affect correctness.

**Autodev exit condition: ZERO blocker bugs, ZERO latent correctness bugs.**
