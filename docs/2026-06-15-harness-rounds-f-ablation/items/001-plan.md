# Item 001 — fc-v4 classifier + pass^k censoring + re-emit reports — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bump the failure classifier fc-v3 → fc-v4 (three honest-bucket row changes) and enforce `pass_pow_k`'s already-declared `censoring_policy="failure"`, then re-emit the M1 reports over existing JSONL — proving taxonomy outputs move while zero `pass^k` numbers move.

**Architecture:** Pure-functional, derived-never-stored reporting layer. The classifier (`reports/classify.py`) is a priority-ordered, first-match-wins, total function that never raises; we extend three rows and add one new closed `Subcategory` value (`budget_exhausted`). The censor lives in shared `metrics/reliability.py` (`pass_pow_k` + `task_reliability`), so the bootstrap-CI helpers and the Fisher-F path in `comparisons.py` inherit it for free. `max_rounds_bound` does not exist on records yet (item 002) — it is read **defensively** via `getattr(..., False)`. No record-schema change; offline re-emit only.

**Tech Stack:** Python 3.13/3.14, pytest, Hypothesis, `uv`, stdlib-only metrics. House style: pure functions, immutability, small functions, TDD red-green-refactor (CLAUDE.md).

---

## Resolved design decisions (read before starting)

**D1 — `budget_exhausted` is a NEW `Subcategory` value (NOT a reuse of `step_exhaustion`).**
Part E row 3 and spec acceptance criterion E.3 both name the target literally: a cap-bound run "classifies as `budget_exhausted`". The existing closed `Subcategory` Literal has no `budget_exhausted`; it has `step_exhaustion` (keyed on the legacy `max_steps` literal the loop emits rarely) and `step_limit_exceeded` (a `grade.failure_reason`). Reusing `step_exhaustion` would conflate a legacy step-truncated run with a `max_rounds`/`safety_cap`-capped run that may have *graded-passed* — losing exactly the distinction §D.1 needs (a capped run is not a reliable success). Minting a new value is also what ADR-0013 mandates (a semantic row change/new subcategory → a classifier version bump → fc-v4). The closed `Subcategory` count goes 19 → 20.

**D2 — Legacy `max_steps` keeps mapping to `step_exhaustion`; only the NEW cap reasons map to `budget_exhausted`.**
This is a judgment call (spec row E.2 lists `max_steps (legacy) + safety_cap + max_rounds` together as "the loop's real stop reasons" the override fires on, without dictating that legacy `max_steps` re-render to a different bucket). Rationale: (a) backward compatibility — the existing green test `test_row_12_max_steps_outranks_red_oracle` and ADR-0013's documented judgment row ("Budget exhaustion (`max_steps`) outranks oracle statuses") both pin `max_steps → step_exhaustion`; churning them re-renders historical taxonomy rows for no semantic gain; (b) `max_steps` is a *truncation* (the loop hard-stopped a turn mid-flight — the existing `step_exhaustion` semantics), whereas `safety_cap`/`max_rounds` are *budget caps* applied at end-of-round with the turn's work kept (§A.2). They are genuinely different mechanisms and deserve different buckets. The cap predicate therefore covers `safety_cap` + `max_rounds` stop reasons **plus** the `safety_cap_bound` / `max_rounds_bound` flags, but **not** `max_steps`.

**D3 — `cap_bound` is computed ONCE in `classify_run` and threaded to both guard points.**
Row E.3 (the row-1 `passed` guard) and Row E.2 (the budget-override for failing runs) read the same predicate. Define one pure helper `_cap_bound(run) -> bool` and call it once; pass the boolean into `_classify_grade_and_budget`. Keeps the predicate single-sourced (no drift between the two rows).

**D4 — The censor predicate is a pure helper in `reliability.py`, shared by `pass_pow_k` + `task_reliability`.**
`_run_passes(run) -> bool` = `run.grade.passed and not (run.trajectory.safety_cap_bound or getattr(run.trajectory, "max_rounds_bound", False))`. Both `pass_pow_k` and `task_reliability` route their per-run boolean through it; the bootstrap-CI helpers and `comparisons.py`'s Fisher-F path already call `task_reliability`, so they inherit the censor unchanged (confirm by test, do not re-implement). `pass_at_1` and `failure_counts` are **untouched** (spec non-goal: §D.1 governs `pass_pow_k`/`task_reliability` only).

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `src/agent_eval_lab/reports/classify.py` | fc-v4 classifier: version bump, `node_execution` leaf, cap-bound override + row-1 guard, new `budget_exhausted` subcategory | Modify |
| `tests/reports/test_classify.py` | per-row unit tests for the three fc-v4 rows + version/vocabulary markers | Modify |
| `tests/reports/test_classify_properties.py` | Hypothesis totality: version label `fc-v4`, `safety_cap_bound` in the strategy | Modify |
| `src/agent_eval_lab/metrics/reliability.py` | `pass_pow_k` + `task_reliability` censoring via `_run_passes` | Modify |
| `tests/metrics/test_reliability.py` | censoring unit tests + bootstrap/Fisher inheritance + 0-moves over historical JSONL | Modify |
| `docs/adr/0013-failure-classification-is-derived-total-and-versioned.md` | fc-v4 amendment | Modify |
| `reports/agentic-v1/M1-F-report.md` | re-emitted report (output of the re-emit command) | Regenerate (output) |

No new source files. No record-schema change.

---

## Task 1: Censor `pass_pow_k` + `task_reliability` (§D.1)

Land the censor first — it is self-contained, has the empirical 0-moves guarantee, and the classifier's `budget_exhausted` bucket is conceptually downstream of "a capped run is not a pass".

**Files:**
- Modify: `src/agent_eval_lab/metrics/reliability.py`
- Test: `tests/metrics/test_reliability.py`

- [ ] **Step 1.1: Extend the test `_run` helper to carry the cap flag**

In `tests/metrics/test_reliability.py`, replace the `_run` helper (lines 14–37) with a version that accepts `safety_cap_bound`:

```python
def _run(
    task_id: str,
    run_index: int,
    passed: bool,
    failure_reason: str | None = None,
    safety_cap_bound: bool = False,
) -> RunResult:
    return RunResult(
        task_id=task_id,
        condition_id="local:qwen3-8b",
        run_index=run_index,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=20, latency_s=0.5),
            run_index=run_index,
            stop_reason="completed",
            safety_cap_bound=safety_cap_bound,
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )
```

- [ ] **Step 1.2: Write the failing censoring tests**

Append to `tests/metrics/test_reliability.py`. Import `task_reliability`, `pass_pow_k_bootstrap_ci`, and `paired_pass_pow_k_diff_ci` at the top (add to the existing `from agent_eval_lab.metrics.reliability import (...)` block):

```python
def test_pass_pow_k_censors_a_capped_pass() -> None:
    # Task X: both runs grade-passed, but one is safety_cap_bound → NOT reliable.
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    assert pass_pow_k(results) == 0.0


def test_task_reliability_censors_a_capped_pass() -> None:
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    assert task_reliability(results) == {"x": False}


def test_pass_pow_k_uncapped_all_pass_is_reliable() -> None:
    results = (_run("x", 0, True), _run("x", 1, True))
    assert pass_pow_k(results) == 1.0


def test_bootstrap_ci_inherits_the_censor() -> None:
    # A capped pass drags the point estimate to 0.0 through task_reliability.
    results = (
        _run("x", 0, True),
        _run("x", 1, True, safety_cap_bound=True),
    )
    ci = pass_pow_k_bootstrap_ci(results, n_resamples=200, seed=1, alpha=0.05)
    assert ci.point == 0.0


def test_defensive_max_rounds_bound_read_when_field_absent() -> None:
    # max_rounds_bound does not exist on records yet (item 002). A run lacking
    # the field must classify exactly as before — an uncapped pass is reliable.
    results = (_run("x", 0, True), _run("x", 1, True))
    assert not hasattr(results[0].trajectory, "max_rounds_bound")
    assert pass_pow_k(results) == 1.0
```

- [ ] **Step 1.3: Run the new tests to verify they fail**

Run: `uv run pytest tests/metrics/test_reliability.py -q -k "censor or inherit or defensive or uncapped"`
Expected: FAIL — `test_pass_pow_k_censors_a_capped_pass` asserts `0.0` but current code returns `1.0` (it keys on `grade.passed` only).

- [ ] **Step 1.4: Add the censor predicate + route both functions through it**

In `src/agent_eval_lab/metrics/reliability.py`, add the helper just below the imports (after the `_require_results` function, before `pass_at_1`):

```python
def _run_passes(run: RunResult) -> bool:
    """A run counts as a pass iff it graded-passed AND was not budget-capped.

    Enforces the pass_pow_k MetricDef's declared censoring_policy="failure"
    (§D.1). safety_cap_bound already exists on the trajectory; max_rounds_bound
    arrives in item 002, so it is read DEFENSIVELY (default False) — every
    existing record (which lacks the field) is unaffected. The censor is GLOBAL
    by design (§10.6): D/B inherit it through this shared module and the Fisher-F
    path in comparisons.py, which both route through task_reliability.
    """
    traj = run.trajectory
    capped = traj.safety_cap_bound or getattr(traj, "max_rounds_bound", False)
    return run.grade.passed and not capped
```

Then change `pass_pow_k` (currently appends `run.grade.passed`):

```python
def pass_pow_k(results: Sequence[RunResult]) -> float:
    _require_results(results)
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(_run_passes(run))
    reliable = sum(1 for passes in by_task.values() if all(passes))
    return reliable / len(by_task)
```

And change `task_reliability` (currently appends `run.grade.passed`):

```python
def task_reliability(results: Sequence[RunResult]) -> dict[str, bool]:
    """Map each task id to whether ALL its runs passed-uncensored (its pass^k
    indicator). A run passes iff grade.passed AND not budget-capped (§D.1)."""
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(_run_passes(run))
    return {tid: all(passes) for tid, passes in by_task.items()}
```

Leave `pass_at_1`, `failure_counts`, `token_totals`, `mean_latency_s`, and both bootstrap-CI helpers byte-unchanged (the helpers route through `_task_reliability = task_reliability`, so they inherit the censor automatically).

- [ ] **Step 1.5: Run the censoring tests to verify they pass**

Run: `uv run pytest tests/metrics/test_reliability.py -q`
Expected: PASS — all tests green (the pre-existing `test_pass_pow_k_is_task_level_reliability` still passes because RESULTS has no capped runs).

- [ ] **Step 1.6: Verify the Fisher-F path inherits the censor (no code change, confirmation test)**

Append to `tests/metrics/test_reliability.py` (this test pins the §D.1/§10.6 global-scope guarantee that `comparisons.py` routes through `task_reliability`):

```python
def test_comparisons_fisher_path_inherits_censor() -> None:
    # comparisons.run_planned_comparisons computes the F (Fisher) success count
    # from task_reliability — a capped pass must drop the success count to 0.
    from agent_eval_lab.metrics.reliability import task_reliability as tr

    capped = (_run("x", 0, True), _run("x", 1, True, safety_cap_bound=True))
    assert sum(tr(capped).values()) == 0
```

Run: `uv run pytest tests/metrics/test_reliability.py::test_comparisons_fisher_path_inherits_censor -q`
Expected: PASS.

- [ ] **Step 1.7: Commit**

```bash
git add src/agent_eval_lab/metrics/reliability.py tests/metrics/test_reliability.py
git commit -m "feat(reliability): censor pass^k on budget-capped runs (D.1)"
```

---

## Task 2: Empirically prove 0 pass^k moves over historical JSONL (§D.1 / §8.8)

A standalone regression test that loads every committed run record and asserts the censor is a provable no-op: no record has `grade.passed=True AND safety_cap_bound=True`. This is the load-bearing "zero numbers move" guarantee.

**Files:**
- Test: `tests/metrics/test_reliability_historical.py` (create)

- [ ] **Step 2.1: Write the historical-invariant test**

Create `tests/metrics/test_reliability_historical.py`:

```python
"""§D.1 verified blast radius: enforcing the pass^k censor moves ZERO historical
pass^k numbers, because no committed record both graded-passed AND was budget-
capped. This test loads every reports/**/*.jsonl run record and proves it."""

import glob
import json
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _iter_records():
    for path in sorted(glob.glob(str(_REPO_ROOT / "reports/**/*.jsonl"), recursive=True)):
        for line in Path(path).read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if "grade" not in row or "trajectory" not in row:
                continue
            yield path, row


def test_no_historical_record_is_a_passed_and_capped_run() -> None:
    offenders = [
        (path, row.get("task_id"), row.get("run_index"))
        for path, row in _iter_records()
        if row["grade"].get("passed") and row["trajectory"].get("safety_cap_bound")
    ]
    assert offenders == [], (
        "the pass^k censor would MOVE these historical numbers (passed=True AND "
        f"safety_cap_bound=True): {offenders}"
    )


def test_historical_corpus_is_non_empty() -> None:
    # Guard against a glob that silently matches nothing (which would make the
    # 0-moves assertion vacuously true).
    assert sum(1 for _ in _iter_records()) >= 1000
```

- [ ] **Step 2.2: Run the historical invariant test**

Run: `uv run pytest tests/metrics/test_reliability_historical.py -q`
Expected: PASS — `offenders == []` and the corpus has ≥1000 records (the committed corpus is ~1430 records, 0 of which are passed-and-capped, confirming the §D.1 verified blast radius).

- [ ] **Step 2.3: Commit**

```bash
git add tests/metrics/test_reliability_historical.py
git commit -m "test(reliability): prove 0 pass^k moves over historical JSONL (D.1)"
```

---

## Task 3: fc-v4 — `node_execution` leaf fix (Row E.1)

`first_execution_evidence` only matches `grader_id == "execution"`. F runs grade with the `node_execution` grader (same evidence shape: `evidence["execution"]=="run"`, `status`, `counts`). A failing F run today falls through to `agent_failure / other_miss`; it should be `agent_failure / oracle_red`.

**Files:**
- Modify: `src/agent_eval_lab/reports/classify.py`
- Test: `tests/reports/test_classify.py`

- [ ] **Step 3.1: Write the failing node-F test (real evidence shape)**

Append to `tests/reports/test_classify.py`. The fixture mirrors a REAL failing node-F record from `reports/agentic-v1/runs-m1-deepseek-deepseek-v4-pro-F.jsonl` (top grade `all_of` → one sub-result `node_execution` with `execution=run`, `status=failed`, `counts={passed:1,failed:4,errors:0,skipped:0}`):

```python
# fc-v4 Row E.1 — node_execution leaf fix ─────────────────────────────────────


def _node_exec_run_evidence(status, counts=None):
    # The node_execution grader emits the SAME evidence shape as the execution
    # grader (graders/node_execution.py::_interpret).
    return {
        "execution": "run",
        "status": status,
        "exit_code": 1,
        "counts": counts or {"passed": 1, "failed": 4, "errors": 0, "skipped": 0},
        "tests": [],
        "stdout": "",
        "stderr": "",
        "execution_hash": "h",
        "displaced_paths": [],
    }


def test_e1_failing_node_execution_leg_is_oracle_red() -> None:
    # Real node-F shape: top grade is all_of with one node_execution sub-result.
    evidence = {
        "sub_results": [
            {
                "grader_id": "node_execution",
                "passed": False,
                "failure_reason": None,
                "evidence": _node_exec_run_evidence("failed"),
            }
        ]
    }
    run = _run(grader_id="all_of", evidence=evidence)
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_e1_top_level_node_execution_grader_is_found() -> None:
    # A top-level node_execution grade (not wrapped in all_of) is also matched.
    run = _run(grader_id="node_execution", evidence=_node_exec_run_evidence("failed"))
    _is(classify_run(run), "agent_failure", "oracle_red")


def test_e1_first_execution_evidence_matches_node_execution() -> None:
    ev = _node_exec_run_evidence("failed")
    assert first_execution_evidence(ev, "node_execution") is ev
```

- [ ] **Step 3.2: Run the node-F tests to verify they fail**

Run: `uv run pytest tests/reports/test_classify.py -q -k "e1"`
Expected: FAIL — `test_e1_failing_node_execution_leg_is_oracle_red` gets `("agent_failure", "other_miss")` because `first_execution_evidence` returns None for the `node_execution` grader_id.

- [ ] **Step 3.3: Accept `node_execution` in `first_execution_evidence`**

In `src/agent_eval_lab/reports/classify.py`, change the guard at the top of `first_execution_evidence` (line ~114):

```python
    if grader_id in ("execution", "node_execution"):
        return evidence
```

(was `if grader_id == "execution":`). Update that function's docstring first line to: `"""The first execution leg's evidence, in declared order (grill Q9; fc-v4 node)."""`.

- [ ] **Step 3.4: Run the node-F tests to verify they pass**

Run: `uv run pytest tests/reports/test_classify.py -q -k "e1"`
Expected: PASS.

- [ ] **Step 3.5: Commit**

```bash
git add src/agent_eval_lab/reports/classify.py tests/reports/test_classify.py
git commit -m "feat(classify): fc-v4 row E.1 — node_execution leaf classifies as oracle_red"
```

---

## Task 4: fc-v4 — add the `budget_exhausted` subcategory + cap-bound override (Rows E.2 + E.3)

Add the new closed `Subcategory` value, a single `_cap_bound` predicate, the row-1 `passed` guard, and the budget override on `safety_cap` + `max_rounds` (legacy `max_steps` stays `step_exhaustion`). See decisions D1–D3.

**Files:**
- Modify: `src/agent_eval_lab/reports/classify.py`
- Test: `tests/reports/test_classify.py`

- [ ] **Step 4.1: Extend the test `_run` helper with `safety_cap_bound`**

In `tests/reports/test_classify.py`, the `_run` helper (lines 21–66) builds the `Trajectory` without `safety_cap_bound`. Add the parameter and thread it. Change the signature line:

```python
def _run(
    *,
    passed=False,
    grader_id="execution",
    evidence=None,
    failure_reason=None,
    stop_reason="completed",
    parse_error=None,
    completion_tokens=5,
    max_tokens=None,
    safety_cap_bound=False,
) -> RunResult:
```

and inside the `Trajectory(...)` constructor add `safety_cap_bound=safety_cap_bound,` immediately after the `max_tokens=max_tokens,` line.

- [ ] **Step 4.2: Write the failing cap-bound tests**

Append to `tests/reports/test_classify.py`:

```python
# fc-v4 Rows E.2 + E.3 — budget-cap override + row-1 guard ──────────────────────


def test_e3_passed_but_safety_cap_bound_is_budget_exhausted() -> None:
    # Row-1 guard: a graded-pass that was budget-capped is NOT "passed".
    run = _run(passed=True, safety_cap_bound=True)
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e3_passed_but_max_rounds_stop_is_budget_exhausted() -> None:
    run = _run(passed=True, stop_reason="max_rounds")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_safety_cap_run_is_budget_exhausted() -> None:
    # A failing run that hit the safety cap outranks its red oracle.
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="safety_cap")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_safety_cap_bound_flag_is_budget_exhausted() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), safety_cap_bound=True)
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_failing_max_rounds_run_is_budget_exhausted() -> None:
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_rounds")
    _is(classify_run(run), "agent_failure", "budget_exhausted")


def test_e2_legacy_max_steps_still_step_exhaustion() -> None:
    # D2: legacy max_steps keeps its truncation bucket (backward compatible).
    run = _run(evidence=_exec_run_evidence("failed"), stop_reason="max_steps")
    _is(classify_run(run), "agent_failure", "step_exhaustion")


def test_e3_passed_uncapped_still_passes() -> None:
    _is(classify_run(_run(passed=True)), "passed", None)
```

Note: the `stop_reason="max_rounds"` values exercise a stop_reason literal not yet in the `Trajectory.stop_reason` Literal — see Step 4.3 for why that is fine (the classifier reads `stop_reason` as a plain string; the test constructs a `Trajectory` with a literal Python value, which `@dataclass` does not runtime-validate against the `Literal` annotation).

- [ ] **Step 4.3: Run the cap-bound tests to verify they fail**

Run: `uv run pytest tests/reports/test_classify.py -q -k "e2 or e3"`
Expected: FAIL — `test_e3_passed_but_safety_cap_bound_is_budget_exhausted` returns `("passed", None)` (row 1 short-circuits); the new subcategory `budget_exhausted` does not exist yet. (`test_e2_legacy_max_steps_still_step_exhaustion` and `test_e3_passed_uncapped_still_passes` already PASS — that is expected; they pin backward compatibility.)

- [ ] **Step 4.4: Add `budget_exhausted` to the closed `Subcategory` Literal**

In `src/agent_eval_lab/reports/classify.py`, in the `Subcategory` Literal (line ~57), add `"budget_exhausted",` immediately after `"step_exhaustion",`:

```python
    "step_limit_exceeded",
    "step_exhaustion",
    "budget_exhausted",  # fc-v4: run hit a budget cap (safety_cap / max_rounds)
    "oracle_timeout",
```

Update the closed-count comment above the Literal (line ~54) to read:

```python
# Closed at 20 values (fc-v4 adds budget_exhausted; fc-v3 added pre_probe_failed,
# post_probe_failed, runner_flagged); versioned with the classifier.  Downstream
# Weeks 9-10 mining joins on (classifier_version, category, subcategory) (ADR-0013).
```

- [ ] **Step 4.5: Add the `_cap_bound` predicate**

In `src/agent_eval_lab/reports/classify.py`, add this helper just below `_classification` (after line ~101, before `first_execution_evidence`):

```python
_CAP_STOP_REASONS = frozenset({"safety_cap", "max_rounds"})


def _cap_bound(run: RunResult) -> bool:
    """fc-v4: did the run hit a budget cap? (safety_cap / max_rounds, §D.1/§E).

    Reads the safety_cap_bound flag (already on the trajectory) and the two cap
    stop reasons. max_rounds_bound arrives in item 002, so it is read DEFENSIVELY
    (default False) — old records lacking the field behave exactly as before.
    Legacy max_steps is a TRUNCATION (step_exhaustion), NOT a budget cap (D2),
    so it is deliberately excluded here.
    """
    traj = run.trajectory
    return (
        traj.safety_cap_bound
        or getattr(traj, "max_rounds_bound", False)
        or traj.stop_reason in _CAP_STOP_REASONS
    )
```

- [ ] **Step 4.6: Guard the row-1 `passed` short-circuit (Row E.3) and thread `cap_bound`**

In `classify_run` (line ~133), replace the row-1 block and the final dispatch line. Change:

```python
def classify_run(run: RunResult) -> RunClassification:
    """fc-v3: priority-ordered, first-match-wins, total — never raises."""
    if run.grade.passed:  # row 1 wins first, even over a recorded parse_failure
        return _classification("passed", None, "grade.passed")
```

to:

```python
def classify_run(run: RunResult) -> RunClassification:
    """fc-v4: priority-ordered, first-match-wins, total — never raises."""
    cap_bound = _cap_bound(run)
    if run.grade.passed and not cap_bound:  # row 1; fc-v4 E.3: cap-bound is not "passed"
        return _classification("passed", None, "grade.passed")
```

Then change the final line of `classify_run` (line ~156):

```python
    return _classify_grade_and_budget(run, exec_ev, cap_bound)  # rows 10-16
```

(was `return _classify_grade_and_budget(run, exec_ev)`).

- [ ] **Step 4.7: Fire the budget override on cap-bound (Row E.2)**

In `_classify_grade_and_budget` (line ~286), change the signature and the `max_steps` row. Change:

```python
def _classify_grade_and_budget(
    run: RunResult, exec_ev: Mapping[str, Any] | None
) -> RunClassification:
    reason = run.grade.failure_reason
```

to:

```python
def _classify_grade_and_budget(
    run: RunResult, exec_ev: Mapping[str, Any] | None, cap_bound: bool
) -> RunClassification:
    reason = run.grade.failure_reason
```

Then, immediately after the `step_limit_exceeded` block (the `if reason == "step_limit_exceeded":` return, line ~294-298) and BEFORE the `if run.trajectory.stop_reason == "max_steps":` block, insert the cap-bound row so it outranks legacy max_steps and the oracle statuses:

```python
    if cap_bound:  # fc-v4 E.2: budget cap (safety_cap / max_rounds) outranks oracle
        return _classification(
            "agent_failure",
            "budget_exhausted",
            f"budget cap hit (stop_reason={run.trajectory.stop_reason!r}, "
            f"safety_cap_bound={run.trajectory.safety_cap_bound})",
        )
    if run.trajectory.stop_reason == "max_steps":  # row 12 outranks rows 13-15
        return _classification(
            "agent_failure", "step_exhaustion", "stop_reason=max_steps"
        )
```

- [ ] **Step 4.8: Run the cap-bound tests to verify they pass**

Run: `uv run pytest tests/reports/test_classify.py -q -k "e2 or e3"`
Expected: PASS.

- [ ] **Step 4.9: Commit**

```bash
git add src/agent_eval_lab/reports/classify.py tests/reports/test_classify.py
git commit -m "feat(classify): fc-v4 rows E.2/E.3 — budget_exhausted on cap-bound runs"
```

---

## Task 5: Bump `CLASSIFIER_VERSION` to fc-v4 + update version/vocabulary markers

**Files:**
- Modify: `src/agent_eval_lab/reports/classify.py`
- Test: `tests/reports/test_classify.py`, `tests/reports/test_classify_properties.py`

- [ ] **Step 5.1: Update the version + vocabulary marker tests (red)**

In `tests/reports/test_classify.py`:

Change `test_classifier_version_is_fc_v3` (line ~306) — rename and update:

```python
def test_classifier_version_is_fc_v4() -> None:
    """The classifier version label is fc-v4 after the budget_exhausted +
    node_execution-leaf bump (item 001)."""
    assert CLASSIFIER_VERSION == "fc-v4"
```

Change `test_fc_v3_version_label` (line ~394) — rename and update:

```python
def test_fc_v4_version_label() -> None:
    assert CLASSIFIER_VERSION == "fc-v4"
```

Change `test_subcategory_vocabulary_is_closed_at_19_after_fc_v3` (line ~462) — rename and update:

```python
def test_subcategory_vocabulary_is_closed_at_20_after_fc_v4() -> None:
    """fc-v4 adds budget_exhausted (fc-v3 added the three env subcategories)."""
    assert len(get_args(Subcategory)) == 20
    assert "budget_exhausted" in get_args(Subcategory)
    for sub in ("pre_probe_failed", "post_probe_failed", "runner_flagged"):
        assert sub in get_args(Subcategory)
```

In `tests/reports/test_classify_properties.py`:

- Add `safety_cap_bound=st.booleans(),` to the `_trajectories = st.builds(Trajectory, ...)` block (after the `max_tokens=...` line, line ~134) and add `"max_rounds",` to the `stop_reason=st.sampled_from([...])` list (after `"safety_cap",`, line ~128) — so the totality property exercises the new cap paths.
- Update the version assertion in `test_classify_run_is_total_and_closed` (line ~154): `assert classification.classifier_version == "fc-v4"`.

- [ ] **Step 5.2: Run the marker tests to verify they fail**

Run: `uv run pytest tests/reports/test_classify.py tests/reports/test_classify_properties.py -q -k "version or vocabulary or total"`
Expected: FAIL — `CLASSIFIER_VERSION` is still `"fc-v3"`.

- [ ] **Step 5.3: Bump the version constant + module docstring**

In `src/agent_eval_lab/reports/classify.py`, change line 44:

```python
CLASSIFIER_VERSION = "fc-v4"
```

Add an fc-v4 section to the module docstring immediately after the `fc-v3 changes from fc-v2` block (before the closing `"""`, line ~34):

```python
fc-v4 changes from fc-v3
-------------------------
- ``node_execution`` leaf: ``first_execution_evidence`` now matches the
  ``"node_execution"`` grader_id (the F-set node oracle, same evidence shape as
  ``"execution"``), so a failing node-F run classifies as ``agent_failure /
  oracle_red`` instead of the catch-all ``other_miss`` (Part E.1).
- ``budget_exhausted`` (agent_failure): a NEW subcategory for runs that hit a
  budget cap — ``stop_reason in {safety_cap, max_rounds}`` or the
  ``safety_cap_bound`` / ``max_rounds_bound`` flags. It outranks the row-1
  ``passed`` short-circuit (a graded-pass that was capped is NOT a reliable
  pass — consistent with §D.1) and the oracle-status rows. Legacy ``max_steps``
  keeps its ``step_exhaustion`` bucket (a truncation, not a budget cap).
  ``max_rounds_bound`` is read defensively (default False) — it arrives on the
  record in item 002, and old records (no field) are unaffected (Part E.2/E.3).
```

- [ ] **Step 5.4: Run the marker tests to verify they pass**

Run: `uv run pytest tests/reports/test_classify.py tests/reports/test_classify_properties.py -q`
Expected: PASS — the full classifier suite is green, including the Hypothesis totality property under fc-v4.

- [ ] **Step 5.5: Update the four OTHER test files that pin the `fc-v3` literal**

The bump breaks any test asserting `fc-v3` because three report modules (`m1.py`, `final.py`) derive their version header from `CLASSIFIER_VERSION`. Make these exact edits (verified present in the tree):

1. `tests/test_committed_runs.py:32` — `assert classification.classifier_version == "fc-v3"` → change to `"fc-v4"`. Also update the module docstring's "fc-v2" reference is fine to leave; only the live assertion matters. (This test parametrizes over `docs/2026-06-11-coding-agent-eval/runs/` and is **skipped** if no committed runs exist there — verify with the run below; if skipped, the edit is still correct for when artifacts land.)
2. `tests/reports/test_m1_build.py:108` — `assert report.classifier_version == "fc-v3"` → change to `"fc-v4"`.
3. `tests/reports/test_final.py:272` — the heading literal `"## Failure classification (fc-v3)"` in the `headings` list → change to `"## Failure classification (fc-v4)"` (the final report derives `({report.classifier_version})` from `CLASSIFIER_VERSION`, [final.py:588](../../../src/agent_eval_lab/reports/final.py)).
4. `tests/reports/test_m1_render.py:70` — `assert "fc-v3" in md or "Failure taxonomy" in md` → change `"fc-v3"` to `"fc-v4"` (the `or` keeps it green either way, but match the new version for clarity).

Then run the whole reports + metrics suite:
Run: `uv run pytest tests/reports tests/metrics tests/test_committed_runs.py -q`
Expected: PASS (with `test_committed_runs_parse_and_classify` possibly SKIPPED if no `docs/2026-06-11-coding-agent-eval/runs/runs-*.jsonl` exist). Do NOT change historical report `.md` artifacts under `reports/` (the M1-F one is regenerated in Task 7; `final.py` / code-repair `.md` outputs are out of this item's scope).

- [ ] **Step 5.6: Commit**

```bash
git add src/agent_eval_lab/reports/classify.py \
        tests/reports/test_classify.py tests/reports/test_classify_properties.py \
        tests/test_committed_runs.py tests/reports/test_m1_build.py \
        tests/reports/test_final.py tests/reports/test_m1_render.py
git commit -m "feat(classify): bump CLASSIFIER_VERSION to fc-v4"
```

---

## Task 6: ADR-0013 fc-v4 amendment

**Files:**
- Modify: `docs/adr/0013-failure-classification-is-derived-total-and-versioned.md`

- [ ] **Step 6.1: Append the fc-v4 amendment**

Append to the end of `docs/adr/0013-failure-classification-is-derived-total-and-versioned.md`:

```markdown
## fc-v4 amendment (2026-06-15)

The harness-rounds/F-ablation phase (design 2026-06-15) requires two declared-
but-unenforced contracts to be honoured in the reporting layer, mandating a
classifier version bump (item 001). fc-v4 (`reports/classify.py`,
`CLASSIFIER_VERSION = "fc-v4"`) changes exactly three rows relative to fc-v3 and
adds one closed-vocabulary value:

- **`node_execution` leaf fix (Row E.1):** `first_execution_evidence` now
  matches the `"node_execution"` grader_id, not only `"execution"`. The F-set
  node oracle (`graders/node_execution.py`) emits the identical evidence shape
  (`execution`/`status`/`counts`), so a failing node-F run now classifies as
  `agent_failure / oracle_red` instead of the catch-all `other_miss`. Verified
  against a real failing node-F record's evidence shape.
- **New subcategory `budget_exhausted` (agent_failure) (Rows E.2/E.3):** a run
  that hit a budget cap — `stop_reason in {safety_cap, max_rounds}` or the
  `safety_cap_bound` / `max_rounds_bound` flags — classifies as
  `agent_failure / budget_exhausted`. It guards the row-1 `passed`
  short-circuit (a graded-pass that was capped is NOT a reliable pass,
  consistent with the §D.1 `pass^k` censor) and outranks the oracle-status rows.
  `max_rounds_bound` is read defensively (default `False`); it arrives on the
  trajectory record in item 002, so item 001 lands standalone and every existing
  record (which lacks the field) is unaffected. The closed `Subcategory`
  vocabulary grows 19 → 20.
- **Legacy `max_steps` is unchanged:** it keeps its `step_exhaustion` bucket. A
  `max_steps` stop is a *turn truncation* (the loop hard-stopped mid-turn),
  semantically distinct from an end-of-round *budget cap*; the documented fc-v1
  judgment row ("`max_steps` outranks oracle statuses") still holds.

Re-rendering the committed M1 reports under fc-v4 moves taxonomy outputs (failing
node-F runs leave `other_miss`; any cap-bound run enters `budget_exhausted`) but
moves **zero `pass^k` numbers**: of the committed historical records, none both
graded-passed and were budget-capped (proven by
`tests/metrics/test_reliability_historical.py`). The Weeks 3-4 / code-repair
workspace-world reports are unaffected (no `node_execution` grader, no cap-bound
runs). Downstream mining keeps joining on
`(classifier_version, category, subcategory)`.
```

- [ ] **Step 6.2: Commit**

```bash
git add docs/adr/0013-failure-classification-is-derived-total-and-versioned.md
git commit -m "docs(adr-0013): fc-v4 amendment — node_execution leaf + budget_exhausted"
```

---

## Task 7: Re-emit the M1-F report + verify taxonomy moves (Part G step 1)

Re-run the M1 report path over the existing F JSONL (offline, no network). Demonstrate the taxonomy moves (`other_miss` → `oracle_red`) and the header now reads `classifier fc-v4`, while the per-domain `pass^k` table is byte-identical to the pre-change report.

**Files:**
- Regenerate (output): `reports/agentic-v1/M1-F-report.md`

- [ ] **Step 7.1: Capture the pre-change pass^k table for the diff guard**

Run (saves the current per-domain pass^k block to a temp file for comparison):

```bash
sed -n '/## Per-domain scores/,/## Macro composite/p' reports/agentic-v1/M1-F-report.md > /tmp/m1f-passk-before.txt
cat /tmp/m1f-passk-before.txt
```

Expected: the F per-domain table with five conditions, all `0.000 [...]` pass^k (this is the number that MUST NOT move).

- [ ] **Step 7.2: Re-emit the M1-F report (the exact offline command)**

Run from the repo root:

```bash
uv run python -m agent_eval_lab.cli report-m1 \
  --spec reports/agentic-v1/M1-spec.frozen.json \
  --runs F:deepseek:deepseek-v4-pro=reports/agentic-v1/runs-m1-deepseek-deepseek-v4-pro-F.jsonl \
         F:glm:Pro/zai-org/GLM-5.1=reports/agentic-v1/runs-m1-glm-Pro-zai-org-GLM-5.1-F.jsonl \
         F:minimax:MiniMax-M3=reports/agentic-v1/runs-m1-minimax-MiniMax-M3-F.jsonl \
         F:siliconflow:Qwen/Qwen3.5-397B-A17B=reports/agentic-v1/runs-m1-siliconflow-Qwen-Qwen3.5-397B-A17B-F.jsonl \
         F:siliconflow:Qwen/Qwen3.6-35B-A3B=reports/agentic-v1/runs-m1-siliconflow-Qwen-Qwen3.6-35B-A3B-F.jsonl \
  --prices evaluator-only/pricing.json \
  --out reports/agentic-v1/M1-F-report.md \
  --seed 20260613 --n-resamples 2000 --alpha 0.05
```

Expected stdout: `reports/agentic-v1/M1-F-report.md` (the command prints the out path and returns 0).

- [ ] **Step 7.3: Verify the header now reads fc-v4**

Run: `grep -n "classifier fc-v4" reports/agentic-v1/M1-F-report.md`
Expected: one match (the header line `- k=5 valid trials · ... · classifier fc-v4`).

- [ ] **Step 7.4: Verify the pass^k table did NOT move (0 numbers move)**

Run:

```bash
sed -n '/## Per-domain scores/,/## Macro composite/p' reports/agentic-v1/M1-F-report.md > /tmp/m1f-passk-after.txt
diff /tmp/m1f-passk-before.txt /tmp/m1f-passk-after.txt && echo "PASS^K UNCHANGED"
```

Expected: `diff` prints nothing and the line `PASS^K UNCHANGED` appears (exit 0) — the per-domain pass^k block is byte-identical, empirically proving the censor moved zero pass^k numbers.

- [ ] **Step 7.5: Verify the taxonomy DID move (other_miss → oracle_red)**

Run:

```bash
grep -c "oracle_red" reports/agentic-v1/M1-F-report.md
grep -c "other_miss" reports/agentic-v1/M1-F-report.md
```

Expected: `oracle_red` count is now > 0 in the failure-taxonomy section (the failing node-F runs that previously bucketed as `other_miss`). Cross-check against the failure analysis: F runs that ran the node oracle and got a red suite should now appear under `agent_failure / oracle_red` rather than `agent_failure / other_miss`. Spot-confirm with:

```bash
sed -n '/## Failure taxonomy/,/## Validity/p' reports/agentic-v1/M1-F-report.md
```

Expected: the per-condition taxonomy tables show `agent_failure | oracle_red | N` rows where the deepseek/minimax F conditions previously showed `other_miss`.

- [ ] **Step 7.6: Commit the regenerated report**

```bash
git add reports/agentic-v1/M1-F-report.md
git commit -m "report(m1): re-emit M1-F under fc-v4 — taxonomy moves, pass^k unchanged"
```

---

## Task 8: Full-suite verification

- [ ] **Step 8.1: Run the entire test suite**

Run: `uv run pytest -q`
Expected: PASS — no regressions. Pay attention to any classifier-version string assertions in `tests/reports/test_m1_render.py`, `tests/reports/test_m1_build.py`, or `tests/reports/test_final.py`; any that asserted `fc-v3` must already have been updated in Step 5.5.

- [ ] **Step 8.2: Run the linter/formatter the repo uses**

Run: `uv run ruff check src/agent_eval_lab/reports/classify.py src/agent_eval_lab/metrics/reliability.py tests/ && uv run ruff format --check src/agent_eval_lab/reports/classify.py src/agent_eval_lab/metrics/reliability.py`
Expected: no errors. (If `ruff format --check` reports a diff, run `uv run ruff format` on the changed files and amend the relevant commit. Note: CI runs `ruff format` over the whole repo — keep formatting clean.)

- [ ] **Step 8.3: Final confirmation — the acceptance criteria checklist**

Verify each spec acceptance criterion has a passing test/check:
- `CLASSIFIER_VERSION == "fc-v4"` → `test_classifier_version_is_fc_v4` (Task 5).
- Row E.1 node_execution leaf → `test_e1_*` (Task 3).
- Row E.2 budget override on safety_cap + max_rounds → `test_e2_*` (Task 4).
- Row E.3 row-1 cap-bound guard → `test_e3_*` (Task 4).
- classifier pure/total/never-raises → `test_classify_run_is_total_and_closed` under fc-v4 (Task 5).
- ADR-0013 fc-v4 amendment → Task 6.
- pass^k censor on `safety_cap_bound OR max_rounds_bound` → Task 1.
- defensive `max_rounds_bound` read → `test_defensive_max_rounds_bound_read_when_field_absent` (Task 1).
- bootstrap/Fisher inherit the censor → Task 1 (Steps 1.6/1.7).
- re-emit M1 reports → Task 7.
- 0 pass^k moves empirically → `test_no_historical_record_is_a_passed_and_capped_run` (Task 2) + the byte-identical diff (Step 7.4).
- taxonomy moves → Step 7.5.

No further commit needed if Step 8.1/8.2 are green and nothing changed.

---

## Notes for the implementer

- **Do NOT create the git branch or push** — the orchestrator handles branch creation and PR/push.
- **Do NOT plumb `max_rounds` / `max_rounds_bound` onto records** — that is item 002. Item 001 only *reads* `max_rounds_bound` defensively (it does not exist on `Trajectory` yet, so `getattr(traj, "max_rounds_bound", False)` is mandatory; a direct attribute access would `AttributeError` and break the classifier's total/never-raises invariant).
- **Do NOT touch `pass_at_1` or `failure_counts`** — §D.1 governs `pass_pow_k` / `task_reliability` only.
- **The censor is global by design** (§10.6 / §D.1) — it lives in shared `reliability.py` and applies to D/B and the Fisher-F path. Do not scope it to F.
- If `tests/metrics/test_reliability_historical.py`'s corpus-floor of `1000` ever drops below that (records pruned from the repo), lower the floor — its purpose is only to prevent a vacuously-true 0-offenders assertion, not to pin an exact count.
