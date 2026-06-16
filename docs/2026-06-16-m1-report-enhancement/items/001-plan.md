# M1 report enhancement (overview + per-domain subreports) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the auto-generated M1 report so the canonical `M1-final-report.md` becomes a thin cross-domain **M1 overview** (with an efficiency/cost rollup, per-domain headlines, and subreport links) and each domain with runs gets a new deterministic per-domain **M1 subreport** (`M1-<domain>-report.md`) carrying per-task / per-condition pass matrices, grader-aware failure gaps, edit signals, task-defect candidates, and efficiency.

**Architecture:** Report-layer-only change (no runner, no scoring). Two new pure adapters — `evidence_summary.py` (grader-aware gap over a `GradeResult`) and `edit_paths.py` (edit signals over a `Trajectory`) — feed a new pure `m1_detail.py` (build + render), mirroring the existing `m1.py` build/render split. A shared `defects.py` is extracted from `final.py` (pure extract-and-import refactor) so the unanimous-fail predicate has one definition. `m1.py` gains overview additions (efficiency rollup, headlines, subreport links, one heading rename). `cli.py` `report-m1` writes the overview plus one subreport per domain into the same directory as `--out`.

**Tech Stack:** Python 3.13 (project targets py311 in ruff), `uv` for env/test running, `pytest` (`uv run pytest`), `ruff` for lint+format (`select = ["E","F","I","UP"]`, `line-length = 88`). Frozen `@dataclass(frozen=True, kw_only=True)` value objects throughout; pure functions, no I/O outside `cli.py`.

---

## Scope boundary — READ FIRST (spec §11)

This is a **REPORT-LAYER ONLY** change. **Do NOT touch:**
- the runner, the graders, or any scoring (`grade.passed`, `grade.score`),
- `pass^k` / pass-pow-k math, CIs, planned-comparison or Pareto math,
- CI config, the frozen `RunResult` / `Trajectory` / `GradeResult` / `ExperimentSpec` schemas,
- any committed run artifact.

The only behavior change to an existing module is the **pure extract-and-import** refactor of `final.py` (move `TaskDefectCandidate` + `_task_defect_candidates` into `reports/defects.py`, import them back). `final.py`'s existing tests (`tests/reports/test_final.py`) MUST stay green — that is the safety net for the refactor.

**Two derivation sources are deliberately separated and MUST NOT be merged (spec §4):**
- `evidence_gap(grade)` reads the **`GradeResult`** only (oracle units, `displaced_paths`). It is the **glossary "displaced path"** signal (oracle-overlay collision).
- `edit_paths(trajectory, target_paths=…)` reads the **`Trajectory`** only (the agent's `str_replace`/`write_file` tool-call targets). Its `out_of_scope` is the **glossary "out-of-scope edit"** signal.

These are different concepts on different records (CONTEXT.md: `displaced path` vs `out-of-scope edit`). Keep them in separate modules; never have one read the other's record.

**Grade-only contract (spec §5 Q6):** `evidence_gap` reads ONLY the `GradeResult`. It NEVER reads the `VerificationSpec`. That is why D yields `oracle_total = None` (the denominator lives on the spec, not the grade) — the F/D asymmetry is inherent and reported honestly.

---

## Verified source facts (cite when implementing — do not re-derive)

All field names below were confirmed against the real source at the cited `file:line`:

- `GradeResult` — `src/agent_eval_lab/records/grade.py:29-35`: `grader_id: str`, `passed: bool`, `score: float`, `evidence: Mapping[str, Any]`, `failure_reason: FailureCategory | None`.
- `RunResult` — `grade.py:38-44`: `task_id`, `condition_id`, `run_index`, `trajectory: Trajectory`, `grade: GradeResult`.
- `Trajectory` — `src/agent_eval_lab/records/trajectory.py:45-90`: `turns: tuple[Turn, ...]`, `usage: Usage`, `run_index`, `stop_reason`, `final_state: Mapping[str,Any] | None`, `rounds: int`, `wall_time_s: float`, `tool_call_counts: Mapping[str,int]`, `safety_cap_bound: bool`, `max_rounds: int | None`, `safety_cap: int | None`, `max_rounds_bound: bool`.
  - **NOTE:** the spec §3 mentions `trajectory.usage.latency_s`; the real field for median time is `trajectory.wall_time_s` (`trajectory.py:73`). `usage.latency_s` exists (`Usage`, `trajectory.py:39-42`) but the existing `efficiency_summary` uses `wall_time_s` for medians. We do NOT add a latency column (spec §8 lists no latency field) — use `wall_time_s` only if a time column is needed; spec §8's efficiency columns do not require wall-time, so omit it.
- `Usage` — `trajectory.py:38-42`: `prompt_tokens: int`, `completion_tokens: int`, `latency_s: float`.
- `ToolCall` — `src/agent_eval_lab/records/turns.py:8-14`: `name: str`, `arguments: Mapping[str, Any]`. `ToolCallTurn` — `turns.py:24-28`: `tool_calls: tuple[ToolCall, ...]`, `content: str | None`. `MessageTurn` — `turns.py:17-21`: `role`, `content`.
- **Edit-tool path key:** both `str_replace` and `write_file` carry the edited path under `arguments["path"]` — confirmed `src/agent_eval_lab/tools/code_world.py:35-71` (`"required": ["path"]` / `["path","content"]` / `["path","old_str","new_str"]`). Code-world edit-tool names: `str_replace`, `write_file` (`src/agent_eval_lab/runners/f_candidate.py:56-57`).
- **`target_paths` location:** lives on `trajectory.final_state["target_paths"]` (seeded into `initial_state["target_paths"]` at `f_candidate.py:122/164`, and `final_state=state` at `src/agent_eval_lab/runners/loop.py:225`). `final_state["files"]` is the produced file tree.
- **`all_of` grade evidence** — `src/agent_eval_lab/graders/composite.py:44-60`: `grader_id == "all_of"`, `evidence["sub_results"]` is a `list[dict]` with keys `grader_id`, `passed`, `failure_reason`, `evidence` (one per sub-spec, declared order).
- **`node_execution` leaf evidence** — `src/agent_eval_lab/graders/node_execution.py:118-139`: `grader_id == "node_execution"`, `evidence = {"execution":"run", "status": <suite status>, "exit_code", "counts": {passed,failed,errors,skipped}, "tests": [[test_id, status], …], "stdout", "stderr", "execution_hash", "displaced_paths": [...]}`. The non-pass branches (`node_execution.py:88-112`) carry `{"execution": "not_run"|"error", ...}` with NO `tests`/`status` keys.
- **`fact_key` grade evidence** — `src/agent_eval_lab/graders/fact_key.py:65-76`: `grader_id == "fact_key"`, pass/fail evidence `{"level", "required_not_on_page": [...], "missing_required": [...], "present_forbidden": [...], "page_snapshot_sha256"}`. The **degraded branch** (`fact_key.py:49-52`) returns `_non_pass({"error": "no assistant message in trajectory"})` — evidence has ONLY the `error` key, none of the fact lists.
- **`marked_failed_not_executed`:** **VERIFIED ABSENT from all of `src/` and from every committed run artifact** (grep found it only in `docs/`). It is a **forward-declared, hypothetical** administrative-record evidence key from the F-ablation phase (drift doc `docs/2026-06-15-harness-rounds-f-ablation/items/001-drift.md:54` describes GLM-F3 administrative records as having "no `execution` key in evidence"). The adapter MUST therefore read it **defensively** — `bool(grade.evidence.get("marked_failed_not_executed", False))` — and never assume the key exists. (Reconciliation note: spec §3 / §5 present it as if present on real records; in fact the only safe contract is a defensive `.get`. Documented here so the impl agent does not hunt for a non-existent producer.)
- `EfficiencySummary` — `src/agent_eval_lab/experiments/aggregate.py:105-112`: `median_rounds: float`, `total_tokens: int`, `median_wall_time_s: float`, `n_censored: int`, `n_runs: int`. **Too thin for §6.6/§7** (no prompt/completion split, no per-tool, no stop_reason counts, no cost) → we add a new `CondDomainEfficiency` (§8 recommendation; do NOT extend `EfficiencySummary`, to avoid touching its Pareto consumers in `m1.py:251-282`).
- `condition_cost_usd(results, condition_id, snapshot)` — `src/agent_eval_lab/experiments/pricing.py:67-84`: **positional** args (not kw-only). Raises `KeyError` if `condition_id` not in `snapshot.prices`. `PricingSnapshot.prices: Mapping[str, PricePoint]` (`pricing.py:29-32`).
- `ReplacementOutcome` — `src/agent_eval_lab/runners/multi_run.py:132-136`: `valid_runs: tuple[RunResult, ...]`, `attempts: tuple[TrialAttempt, ...]`, `void: bool`. `TrialAttempt` — `multi_run.py:125-129`: `attempt_index: int`, `valid: bool`, `run: RunResult`.
- `classify_run(run) -> RunClassification` and `CLASSIFIER_VERSION` (`"fc-v4"`) — `src/agent_eval_lab/reports/classify.py` (imported by both `m1.py:34-38` and `final.py:30-34`). `RunClassification` carries `.category` and `.subcategory` (`m1.py:121-122`).
- **Existing heading to rename** — `src/agent_eval_lab/reports/m1.py:374`: `f"## Failure taxonomy ({report.classifier_version}) per condition"` → `f"## Failure classification ({report.classifier_version}) per condition"`. Glossary `RunClassification` reserves "failure taxonomy" for `FailureCategory`; `final.py:588` already uses "Failure classification".
- **CLI** — `_run_report_m1` at `src/agent_eval_lab/cli.py:1172-1200`; `report-m1` argparse at `cli.py:1558-1575`; dispatch at `cli.py:1601-1602`. `render_m1` is `from agent_eval_lab.reports.m1 import render_markdown as render_m1` (`cli.py:52`). `_atomic_write(path, content)` at `cli.py:139`. `_parse_domain_runs_spec` at `cli.py:1110`.

---

## Test command (CONFIRMED)

The project uses `uv` (`pyproject.toml` + `uv.lock` present; no Makefile, no CONTRIBUTING). `pyproject.toml:28-30` sets `[tool.pytest.ini_options] addopts = "-q"`, `testpaths = ["tests"]`. Ruff is configured (`pyproject.toml:32-37`, `select=["E","F","I","UP"]`, `line-length=88`).

- Run one test file: `uv run pytest tests/reports/test_evidence_summary.py -q`
- Run one test: `uv run pytest tests/reports/test_evidence_summary.py::test_name -v`
- Full suite: `uv run pytest`
- Lint: `uv run ruff check src tests`
- Format check: `uv run ruff format --check src tests` (apply with `uv run ruff format src tests`)

A smoke run of `uv run pytest tests/reports/test_m1_render.py -q` passed during planning, confirming the command.

---

## File Structure

**Create:**
- `src/agent_eval_lab/reports/evidence_summary.py` — `EvidenceGap` + `evidence_gap(grade)` (grade-only, grader-aware adapter).
- `src/agent_eval_lab/reports/edit_paths.py` — `EditPaths` + `edit_paths(trajectory, target_paths=…)` (trajectory-derived edit signals).
- `src/agent_eval_lab/reports/defects.py` — `TaskDefectCandidate` + `task_defect_candidates(...)` (extracted from `final.py`, shared).
- `src/agent_eval_lab/reports/m1_detail.py` — `CondDomainEfficiency`, the per-domain detail value objects, `build_m1_detail(...)`, `render_detail(...)`, and the shared efficiency builder `cond_domain_efficiency(...)`.
- `tests/reports/test_evidence_summary.py`
- `tests/reports/test_edit_paths.py`
- `tests/reports/test_defects.py`
- `tests/reports/test_m1_detail_build.py`
- `tests/reports/test_m1_detail_render.py`
- `tests/reports/test_m1_detail_determinism.py`

**Modify:**
- `src/agent_eval_lab/reports/final.py` — remove the local `TaskDefectCandidate` + `_task_defect_candidates`; import from `reports/defects.py`; keep its public render byte-identical.
- `src/agent_eval_lab/reports/m1.py` — add efficiency rollup, per-domain headlines, subreport links; rename the `m1.py:374` heading.
- `tests/reports/test_m1_render.py` — update the heading assertion (line 70) and add efficiency-rollup + subreport-link assertions.
- `src/agent_eval_lab/cli.py` — `report-m1` argparse (`--subreports/--no-subreports` default on, `--subreport-dir`) + `_run_report_m1` wiring to write subreports.

---

## TDD ordering (build the leaves first, then the tree)

1. **Task 1** — `reports/defects.py` extract-and-import refactor (lowest-risk; unblocks `m1_detail` reuse; `final.py` tests are the net).
2. **Task 2** — `reports/evidence_summary.py` (grade-only adapter).
3. **Task 3** — `reports/edit_paths.py` (trajectory adapter).
4. **Task 4** — `reports/m1_detail.py` efficiency builder `CondDomainEfficiency` + `cond_domain_efficiency()`.
5. **Task 5** — `reports/m1_detail.py` `build_m1_detail()` (per-task detail value objects, defect reuse, classify reuse).
6. **Task 6** — `reports/m1_detail.py` `render_detail()` (markdown subreport).
7. **Task 7** — `reports/m1_detail.py` determinism test (byte-identical).
8. **Task 8** — `reports/m1.py` overview additions (efficiency rollup, headlines, subreport links, heading rename) + `test_m1_render.py` update.
9. **Task 9** — `cli.py` `report-m1` wiring (subreports written beside `--out`).
10. **Task 10** — Full-suite + lint/format verification.

---

### Task 1: Extract `defects.py` from `final.py` (pure extract-and-import)

**Files:**
- Create: `src/agent_eval_lab/reports/defects.py`
- Create: `tests/reports/test_defects.py`
- Modify: `src/agent_eval_lab/reports/final.py:96-101` (delete `TaskDefectCandidate`), `final.py:251-273` (delete `_task_defect_candidates`), `final.py:357` (call site), and the import block (`final.py:29-34` area) to import from `reports/defects.py`.

The current code (verbatim, `final.py:96-101` and `final.py:251-273`):

```python
@dataclass(frozen=True, kw_only=True)
class TaskDefectCandidate:
    task_id: str
    n_conditions: int  # non-blocked conditions WITH records for the task
    n_runs: int  # total recorded runs over those conditions


def _task_defect_candidates(
    conditions: Sequence[FinalConditionInput],
) -> tuple[TaskDefectCandidate, ...]:
    """Tasks failing ALL recorded runs on EVERY non-blocked condition with
    records for them (grill Q10): a condition with no records for a task
    contributes nothing (vacuous); blocked conditions are excluded entirely.
    Flagged for human review, never auto-classified (ADR-0013)."""
    live = [c for c in conditions if c.blocked_reason is None and c.results]
    per_task: dict[str, dict[str, list[bool]]] = {}
    for cond in live:
        for run in cond.results:
            per_task.setdefault(run.task_id, {}).setdefault(cond.label, []).append(
                run.grade.passed
            )
    return tuple(
        TaskDefectCandidate(
            task_id=task_id,
            n_conditions=len(per_task[task_id]),
            n_runs=sum(len(passes) for passes in per_task[task_id].values()),
        )
        for task_id in sorted(per_task)
        if not any(any(passes) for passes in per_task[task_id].values())
    )
```

The predicate keys on `cond.label` and reads `run.task_id` + `run.grade.passed` — it depends only on the structural shape `(label, results-with .task_id/.grade.passed, blocked_reason)`. To make it reusable by the M1 subreport (which has no `FinalConditionInput`), the extracted function takes a **generic sequence of (label, runs) groups plus a blocked predicate**. We keep `final.py`'s exact behavior by having `final.py` adapt its `FinalConditionInput`s to the generic shape.

- [ ] **Step 1: Write the failing test** (`tests/reports/test_defects.py`)

```python
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.defects import (
    DefectInputGroup,
    TaskDefectCandidate,
    task_defect_candidates,
)


def _run(task_id, cond, passed, idx=0):
    return RunResult(
        task_id=task_id,
        condition_id=cond,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
            run_index=idx,
            stop_reason="completed_natural",
            rounds=1,
        ),
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def test_unanimous_fail_is_a_candidate():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", False),), blocked=False),
    )
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=2, n_runs=2),)


def test_one_condition_passing_is_not_a_candidate():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", True),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", False),), blocked=False),
    )
    assert task_defect_candidates(groups) == ()


def test_vacuous_condition_without_records_does_not_block():
    # B has no records for t1 -> contributes nothing; A fails t1 unanimously.
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t2", "B", True),), blocked=False),
    )
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=1, n_runs=1),)


def test_blocked_condition_is_excluded():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", True),), blocked=True),
    )
    # B is blocked -> excluded; A fails t1 unanimously -> candidate.
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=1, n_runs=1),)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_defects.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.defects'`.

- [ ] **Step 3: Write `reports/defects.py`**

```python
"""Shared task-defect-candidate predicate (extracted from final.py, ADR-0013).

A task-defect candidate is a task id that every non-blocked group WITH records
for it unanimously fails (all recorded runs). Flagged for human review, never
auto-classified as task_failure: conformance already proves solvability, oracle
breadth, and symptom reality, so unanimity defaults to "hard, not defective".
Pure; one glossary-critical definition (DRY) shared by final.py and the M1
subreport.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class DefectInputGroup:
    """One condition's runs for the predicate: a label, its runs, and whether
    the condition is blocked (blocked groups are excluded entirely)."""

    label: str
    runs: Sequence[RunResult]
    blocked: bool = False


@dataclass(frozen=True, kw_only=True)
class TaskDefectCandidate:
    task_id: str
    n_conditions: int  # non-blocked groups WITH records for the task
    n_runs: int  # total recorded runs over those groups


def task_defect_candidates(
    groups: Sequence[DefectInputGroup],
) -> tuple[TaskDefectCandidate, ...]:
    """Tasks failing ALL recorded runs on EVERY non-blocked group with records
    for them: a group with no records for a task contributes nothing (vacuous);
    blocked groups are excluded entirely. Flagged for human review, never
    auto-classified (ADR-0013)."""
    live = [g for g in groups if not g.blocked and g.runs]
    per_task: dict[str, dict[str, list[bool]]] = {}
    for group in live:
        for run in group.runs:
            per_task.setdefault(run.task_id, {}).setdefault(group.label, []).append(
                run.grade.passed
            )
    return tuple(
        TaskDefectCandidate(
            task_id=task_id,
            n_conditions=len(per_task[task_id]),
            n_runs=sum(len(passes) for passes in per_task[task_id].values()),
        )
        for task_id in sorted(per_task)
        if not any(any(passes) for passes in per_task[task_id].values())
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_defects.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Refactor `final.py` to import from `defects.py`**

In `src/agent_eval_lab/reports/final.py`:

1. Add to the import block (near `final.py:29-34`):

```python
from agent_eval_lab.reports.defects import (
    DefectInputGroup,
    TaskDefectCandidate,
    task_defect_candidates,
)
```

2. Delete the local `TaskDefectCandidate` dataclass (`final.py:96-101`).

3. Delete the local `_task_defect_candidates` function (`final.py:251-273`).

4. Replace the build call site (`final.py:357`, currently `task_defect_candidates=_task_defect_candidates(conditions),`) with an adapter that maps `FinalConditionInput` → `DefectInputGroup`:

```python
        task_defect_candidates=task_defect_candidates(
            tuple(
                DefectInputGroup(
                    label=c.label,
                    runs=tuple(c.results),
                    blocked=c.blocked_reason is not None,
                )
                for c in conditions
            )
        ),
```

> Behavior is preserved: the old predicate filtered `c.blocked_reason is None and c.results`; the new one filters `not g.blocked and g.runs`. A `FinalConditionInput` with `blocked_reason is not None` maps to `blocked=True`; one with empty `results` maps to empty `runs` → both excluded by `live`, identical to before. `TaskDefectCandidate` is the same dataclass (now imported), so `FinalReport.task_defect_candidates` annotation still resolves.

- [ ] **Step 6: Run final.py's tests (the safety net) + defects test**

Run: `uv run pytest tests/reports/test_final.py tests/reports/test_defects.py -q`
Expected: PASS (all green; no behavior change in `final.py`).

- [ ] **Step 7: Commit**

```bash
git add src/agent_eval_lab/reports/defects.py tests/reports/test_defects.py src/agent_eval_lab/reports/final.py
git commit -m "refactor(reports): extract task-defect predicate into shared defects.py"
```

**Verification point:** `tests/reports/test_final.py` and `tests/reports/test_defects.py` both green. The extract is byte-neutral for `final.py`'s render.

---

### Task 2: `reports/evidence_summary.py` — grader-aware gap adapter (spec §5)

**Files:**
- Create: `src/agent_eval_lab/reports/evidence_summary.py`
- Create: `tests/reports/test_evidence_summary.py`

`EvidenceGap` signature (spec §5, verbatim):

```python
@dataclass(frozen=True, kw_only=True)
class EvidenceGap:
    grader_id: str
    oracle_total: int | None        # F: len(tests); D: None (no denominator in grade — Q6)
    oracle_passed: int | None       # F: #tests passed; D: None
    failing_units: tuple[str, ...]  # F: failing test names; D: missing_required + present_forbidden
    displaced_paths: tuple[str, ...]  # oracle-overlay collisions (F node_execution); else ()
    administrative: bool            # marked_failed_not_executed (defensive .get)
    status: str                     # "passed" | "failed" | "incomplete" | "not_executed" | "no_answer"
```

Dispatch rules (spec §5, grounded in the verified evidence shapes):
- `grader_id == "all_of"`: walk `evidence["sub_results"]` to the **first** sub-result whose `grader_id == "node_execution"`; adapt that leaf's `evidence`. If none, fall to the unknown path with `status` from `grade.passed`.
- `grader_id == "node_execution"` (or the walked leaf): if `evidence` has a `tests` list → `oracle_total = len(tests)`, `oracle_passed = #[t for t in tests if t[1] == "passed"]`, `failing_units = tuple(name for name, st in tests if st != "passed")`, `displaced_paths = tuple(evidence.get("displaced_paths", ()))`, `status = "passed" if grade.passed else "failed"`. If `evidence` lacks `tests` (the `not_run`/`error` branches) → `oracle_total=None, oracle_passed=None, failing_units=(), status="not_executed"`.
- `grader_id == "fact_key"`: if `evidence` has the degraded `{"error": "no assistant message in trajectory"}` (no `missing_required` key) → `status="no_answer"`, `failing_units=()`, `oracle_total=None`. Else `oracle_total=None, oracle_passed=None`, `failing_units = tuple(missing_required) + tuple(present_forbidden)`, `displaced_paths=()`, `status="passed" if grade.passed else "failed"`.
- **Administrative override (defensive):** if `bool(grade.evidence.get("marked_failed_not_executed", False))` is True → `administrative=True, status="not_executed"`, `oracle_total=None, oracle_passed=None, failing_units=(), displaced_paths=()`. (Check this FIRST so an administrative record never tries to read `tests`.)
- **Unknown grader:** minimal gap — `oracle_total=None, oracle_passed=None, failing_units=(), displaced_paths=(), status="passed" if grade.passed else "failed"`. **Never raises** (spec §5, risk §12).

- [ ] **Step 1: Write the failing test** (`tests/reports/test_evidence_summary.py`)

```python
from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.reports.evidence_summary import EvidenceGap, evidence_gap


def _grade(grader_id, passed, evidence):
    return GradeResult(
        grader_id=grader_id, passed=passed, score=1.0 if passed else 0.0,
        evidence=evidence,
    )


def test_node_execution_failing_tests_and_displaced():
    grade = _grade(
        "node_execution", False,
        {
            "execution": "run", "status": "failed",
            "counts": {"passed": 1, "failed": 2, "errors": 0, "skipped": 0},
            "tests": [["a", "passed"], ["b", "failed"], ["c", "failed"]],
            "displaced_paths": ["tests/test_app.js"],
        },
    )
    gap = evidence_gap(grade)
    assert gap == EvidenceGap(
        grader_id="node_execution", oracle_total=3, oracle_passed=1,
        failing_units=("b", "c"), displaced_paths=("tests/test_app.js",),
        administrative=False, status="failed",
    )


def test_node_execution_passed():
    grade = _grade(
        "node_execution", True,
        {"execution": "run", "status": "passed", "tests": [["a", "passed"]],
         "displaced_paths": []},
    )
    gap = evidence_gap(grade)
    assert gap.status == "passed"
    assert gap.oracle_total == 1 and gap.oracle_passed == 1
    assert gap.failing_units == ()


def test_node_execution_not_run_branch_has_no_tests():
    grade = _grade(
        "node_execution", False,
        {"execution": "not_run", "reason": "missing_final_state"},
    )
    gap = evidence_gap(grade)
    assert gap.oracle_total is None and gap.oracle_passed is None
    assert gap.failing_units == () and gap.status == "not_executed"


def test_all_of_walks_to_node_execution_leaf():
    grade = _grade(
        "all_of", False,
        {"sub_results": [
            {"grader_id": "node_execution", "passed": False, "failure_reason": None,
             "evidence": {"execution": "run", "status": "failed",
                          "tests": [["x", "failed"]], "displaced_paths": []}},
        ]},
    )
    gap = evidence_gap(grade)
    assert gap.grader_id == "node_execution"
    assert gap.oracle_total == 1 and gap.failing_units == ("x",)
    assert gap.status == "failed"


def test_fact_key_missing_and_forbidden():
    grade = _grade(
        "fact_key", False,
        {"level": "L1", "required_not_on_page": [],
         "missing_required": ["price"], "present_forbidden": ["refund"],
         "page_snapshot_sha256": "abc"},
    )
    gap = evidence_gap(grade)
    assert gap.oracle_total is None and gap.oracle_passed is None
    assert gap.failing_units == ("price", "refund")
    assert gap.displaced_paths == () and gap.status == "failed"


def test_fact_key_no_answer_degraded_branch():
    grade = _grade("fact_key", False,
                   {"error": "no assistant message in trajectory"})
    gap = evidence_gap(grade)
    assert gap.status == "no_answer"
    assert gap.failing_units == () and gap.oracle_total is None


def test_administrative_marked_failed_not_executed():
    grade = _grade("node_execution", False,
                   {"marked_failed_not_executed": True})
    gap = evidence_gap(grade)
    assert gap.administrative is True
    assert gap.status == "not_executed"
    assert gap.oracle_total is None and gap.failing_units == ()


def test_unknown_grader_never_raises():
    grade = _grade("some_future_grader", True, {"whatever": 1})
    gap = evidence_gap(grade)
    assert gap.grader_id == "some_future_grader"
    assert gap.status == "passed"
    assert gap.oracle_total is None and gap.failing_units == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_evidence_summary.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.evidence_summary'`.

- [ ] **Step 3: Write `reports/evidence_summary.py`**

```python
"""Grader-aware gap adapter: one GradeResult -> a small render-ready EvidenceGap.

GRADE-ONLY (spec §5 Q6): reads only the GradeResult — NEVER the VerificationSpec.
That is why D (fact_key) yields oracle_total=None: the denominator lives on the
spec, not the grade. The ONLY place that knows evidence internals, so adding a
new grader is one new branch + its test; an unknown grader degrades gracefully
(never raises). The displaced_paths it carries are the glossary "displaced path"
signal (oracle-overlay collision) — NOT out-of-scope edits (those are
trajectory-derived; see reports/edit_paths.py).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.records.grade import GradeResult


@dataclass(frozen=True, kw_only=True)
class EvidenceGap:
    grader_id: str
    oracle_total: int | None
    oracle_passed: int | None
    failing_units: tuple[str, ...]
    displaced_paths: tuple[str, ...]
    administrative: bool
    status: str


def _unknown(grade: GradeResult) -> EvidenceGap:
    return EvidenceGap(
        grader_id=grade.grader_id,
        oracle_total=None,
        oracle_passed=None,
        failing_units=(),
        displaced_paths=(),
        administrative=False,
        status="passed" if grade.passed else "failed",
    )


def _node_execution(grader_id: str, passed: bool, ev: Mapping[str, Any]) -> EvidenceGap:
    tests = ev.get("tests")
    if not isinstance(tests, Sequence):
        # not_run / error branch: no per-test detail in evidence.
        return EvidenceGap(
            grader_id=grader_id,
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=tuple(ev.get("displaced_paths", ())),
            administrative=False,
            status="not_executed",
        )
    total = len(tests)
    passed_count = sum(1 for _name, st in tests if st == "passed")
    failing = tuple(name for name, st in tests if st != "passed")
    return EvidenceGap(
        grader_id=grader_id,
        oracle_total=total,
        oracle_passed=passed_count,
        failing_units=failing,
        displaced_paths=tuple(ev.get("displaced_paths", ())),
        administrative=False,
        status="passed" if passed else "failed",
    )


def _fact_key(passed: bool, ev: Mapping[str, Any]) -> EvidenceGap:
    if "missing_required" not in ev:
        # degraded: {"error": "no assistant message in trajectory"}
        return EvidenceGap(
            grader_id="fact_key",
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=(),
            administrative=False,
            status="no_answer",
        )
    failing = tuple(ev.get("missing_required", ())) + tuple(
        ev.get("present_forbidden", ())
    )
    return EvidenceGap(
        grader_id="fact_key",
        oracle_total=None,
        oracle_passed=None,
        failing_units=failing,
        displaced_paths=(),
        administrative=False,
        status="passed" if passed else "failed",
    )


def evidence_gap(grade: GradeResult) -> EvidenceGap:
    ev = grade.evidence
    # Administrative override first: an administrative record carries no oracle.
    if bool(ev.get("marked_failed_not_executed", False)):
        return EvidenceGap(
            grader_id=grade.grader_id,
            oracle_total=None,
            oracle_passed=None,
            failing_units=(),
            displaced_paths=(),
            administrative=True,
            status="not_executed",
        )
    if grade.grader_id == "all_of":
        leaf = next(
            (
                sr
                for sr in ev.get("sub_results", ())
                if sr.get("grader_id") == "node_execution"
            ),
            None,
        )
        if leaf is not None:
            return _node_execution("node_execution", leaf["passed"], leaf["evidence"])
        return _unknown(grade)
    if grade.grader_id == "node_execution":
        return _node_execution("node_execution", grade.passed, ev)
    if grade.grader_id == "fact_key":
        return _fact_key(grade.passed, ev)
    return _unknown(grade)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_evidence_summary.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/evidence_summary.py tests/reports/test_evidence_summary.py
git commit -m "feat(reports): grader-aware evidence_gap adapter (grade-only, spec §5)"
```

**Verification point:** all 8 cases green; the unknown-grader case proves totality (never raises).

---

### Task 3: `reports/edit_paths.py` — trajectory-derived edit signals (spec §5a)

**Files:**
- Create: `src/agent_eval_lab/reports/edit_paths.py`
- Create: `tests/reports/test_edit_paths.py`

`EditPaths` signature (spec §5a, verbatim):

```python
@dataclass(frozen=True, kw_only=True)
class EditPaths:
    edited: tuple[str, ...]         # paths targeted by str_replace / write_file tool calls
    out_of_scope: tuple[str, ...]   # edited − target_paths (CONTEXT.md "out-of-scope edit")
```

`edit_paths(trajectory, *, target_paths)`:
- Walk `trajectory.turns`; for each `ToolCallTurn`, for each `ToolCall` whose `name in {"str_replace", "write_file"}`, collect `call.arguments.get("path")` (skip if missing/None — fail-quiet). An unknown edit-tool contributes no path.
- `edited = tuple(sorted(set(collected)))` (deterministic, dedup).
- `out_of_scope = tuple(p for p in edited if p not in set(target_paths))`.
- **Descriptive, never a verdict** (CONTEXT.md "out-of-scope edit"; F has no `OnlyModifies` leg).

- [ ] **Step 1: Write the failing test** (`tests/reports/test_edit_paths.py`)

```python
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.reports.edit_paths import EditPaths, edit_paths


def _traj(turns):
    return Trajectory(
        turns=tuple(turns),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="completed_natural",
        rounds=len(turns),
    )


def test_collects_str_replace_and_write_file_targets():
    traj = _traj([
        MessageTurn(role="assistant", content="ok"),
        ToolCallTurn(tool_calls=(
            ToolCall(name="str_replace", arguments={"path": "wdio.conf.ts"}),
            ToolCall(name="write_file", arguments={"path": "index.ts", "content": "x"}),
        )),
    ])
    out = edit_paths(traj, target_paths=("wdio.conf.ts",))
    assert out == EditPaths(
        edited=("index.ts", "wdio.conf.ts"),
        out_of_scope=("index.ts",),
    )


def test_dedups_repeated_edits():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(name="str_replace", arguments={"path": "a.ts"}),
            ToolCall(name="str_replace", arguments={"path": "a.ts"}),
        )),
    ])
    out = edit_paths(traj, target_paths=("a.ts",))
    assert out.edited == ("a.ts",)
    assert out.out_of_scope == ()


def test_unknown_edit_tool_contributes_no_path():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(name="read_file", arguments={"path": "a.ts"}),
            ToolCall(name="list_files", arguments={}),
        )),
    ])
    out = edit_paths(traj, target_paths=("a.ts",))
    assert out.edited == ()
    assert out.out_of_scope == ()


def test_missing_path_argument_is_fail_quiet():
    traj = _traj([
        ToolCallTurn(tool_calls=(
            ToolCall(name="write_file", arguments={"content": "x"}),
        )),
    ])
    out = edit_paths(traj, target_paths=())
    assert out.edited == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_edit_paths.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.edit_paths'`.

- [ ] **Step 3: Write `reports/edit_paths.py`**

```python
"""Trajectory-derived edit signals: which paths the agent edited, and which lie
outside the task's declared target_paths (the glossary "out-of-scope edit").

Reads ONLY the Trajectory (the agent's str_replace/write_file tool-call targets)
plus the declared target_paths. DESCRIPTIVE, never a verdict — F has no
OnlyModifies leg, so an out-of-scope edit is reported, never auto-failed. Kept
separate from evidence_summary.py: out-of-scope edit (trajectory) and displaced
path (grade, oracle-overlay collision) are different concepts (CONTEXT.md) on
different records and must not be merged (spec §4).
"""

from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import ToolCallTurn

# Code-world edit tools (f_candidate.py:56-57). An unknown tool contributes no
# edited path (fail-quiet).
_EDIT_TOOLS = frozenset({"str_replace", "write_file"})


@dataclass(frozen=True, kw_only=True)
class EditPaths:
    edited: tuple[str, ...]
    out_of_scope: tuple[str, ...]


def edit_paths(trajectory: Trajectory, *, target_paths: Sequence[str]) -> EditPaths:
    collected: set[str] = set()
    for turn in trajectory.turns:
        if not isinstance(turn, ToolCallTurn):
            continue
        for call in turn.tool_calls:
            if call.name not in _EDIT_TOOLS:
                continue
            path = call.arguments.get("path")
            if isinstance(path, str):
                collected.add(path)
    edited = tuple(sorted(collected))
    in_scope = set(target_paths)
    out_of_scope = tuple(p for p in edited if p not in in_scope)
    return EditPaths(edited=edited, out_of_scope=out_of_scope)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_edit_paths.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/edit_paths.py tests/reports/test_edit_paths.py
git commit -m "feat(reports): trajectory-derived edit_paths signals (out-of-scope, spec §5a)"
```

**Verification point:** edited dedup'd + sorted; `out_of_scope = edited − target_paths`; unknown tool / missing path are fail-quiet.

---

### Task 4: `reports/m1_detail.py` — efficiency builder `CondDomainEfficiency` (spec §8)

**Files:**
- Create: `src/agent_eval_lab/reports/m1_detail.py` (start the module with the efficiency builder)
- Create: `tests/reports/test_m1_detail_build.py` (start with the efficiency cases; more added in Task 5)

`CondDomainEfficiency` signature (spec §8). Recommendation per spec §8: **new value object, do NOT extend `EfficiencySummary`** (avoids touching its Pareto consumers).

```python
@dataclass(frozen=True, kw_only=True)
class CondDomainEfficiency:
    # time-to-completion — RIGHT-CENSORED for budget-capped runs (glossary: censoring)
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int                 # runs in the group that are budget-capped
    cap_bound: int | None               # the cap the censored runs hit (max_rounds / safety_cap)
    # resource — OBSERVED, summed over ALL valid runs incl. capped (never censored)
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None              # condition_cost_usd over the group's valid runs
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int                # stop_reason == "safety_cap" (backstop)
    max_rounds_hits: int                # stop_reason == "max_rounds" (primary budget, F-ablation)
    stop_reason_counts: Mapping[str, int]
```

`cond_domain_efficiency(*, runs, condition_id, pricing)`:
- `runs` is a `Sequence[RunResult]` (the group's **valid** runs — works for a whole (cond, domain) or a single task's valid runs, spec §8).
- Empty `runs` → a zero summary: `rounds_median=0.0, rounds_min=0, rounds_max=0, censored_count=0, cap_bound=None, prompt_tokens=0, completion_tokens=0, total_tokens=0, cost_usd=None, tool_call_totals={}, safety_cap_hits=0, max_rounds_hits=0, stop_reason_counts={}`.
- `rounds_median = statistics.median(r.trajectory.rounds for r in runs)`; `rounds_min = min(...)`, `rounds_max = max(...)`.
- **Censored** iff `r.trajectory.safety_cap_bound or r.trajectory.max_rounds_bound` (glossary `censoring`). `censored_count = #censored`.
- `cap_bound`: the cap a censored run hit. Prefer `r.trajectory.max_rounds` when `max_rounds_bound`, else `r.trajectory.safety_cap` when `safety_cap_bound`; take the first censored run's bound deterministically (runs are in record order). `None` when `censored_count == 0`.
- `prompt_tokens = sum(r.trajectory.usage.prompt_tokens)`, `completion_tokens = sum(r.trajectory.usage.completion_tokens)`, `total_tokens = prompt + completion` — over ALL valid runs incl. capped (observed, never censored).
- `tool_call_totals`: merge `r.trajectory.tool_call_counts` summing per tool; render-sorted later. Return as a plain `dict` built by sorted-key accumulation for determinism.
- `safety_cap_hits = #[r for r ... stop_reason == "safety_cap"]`; `max_rounds_hits = #[... stop_reason == "max_rounds"]`.
- `stop_reason_counts`: count over `r.trajectory.stop_reason`, built by sorted-key accumulation.
- `cost_usd`: `condition_cost_usd(runs, condition_id, pricing)` (positional args, `pricing.py:67`) iff `condition_id in pricing.prices and runs`, else `None`.

- [ ] **Step 1: Write the failing test** (`tests/reports/test_m1_detail_build.py`)

```python
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import (
    CondDomainEfficiency,
    cond_domain_efficiency,
)

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _run(
    task_id, idx, *, rounds, prompt, completion, stop="completed_natural",
    safety_cap_bound=False, max_rounds_bound=False, max_rounds=None, safety_cap=None,
    tool_calls=None, passed=False,
):
    return RunResult(
        task_id=task_id,
        condition_id=_COND,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=prompt, completion_tokens=completion,
                        latency_s=1.0),
            run_index=idx,
            stop_reason=stop,
            rounds=rounds,
            tool_call_counts=tool_calls or {},
            safety_cap_bound=safety_cap_bound,
            max_rounds_bound=max_rounds_bound,
            max_rounds=max_rounds,
            safety_cap=safety_cap,
        ),
        grade=GradeResult(grader_id="g", passed=passed,
                          score=1.0 if passed else 0.0, evidence={}),
    )


def test_empty_runs_is_zero_summary():
    eff = cond_domain_efficiency(runs=(), condition_id=_COND, pricing=_PRICING)
    assert eff == CondDomainEfficiency(
        rounds_median=0.0, rounds_min=0, rounds_max=0, censored_count=0,
        cap_bound=None, prompt_tokens=0, completion_tokens=0, total_tokens=0,
        cost_usd=None, tool_call_totals={}, safety_cap_hits=0, max_rounds_hits=0,
        stop_reason_counts={},
    )


def test_tokens_observed_over_all_runs_including_capped():
    runs = (
        _run("t1", 0, rounds=5, prompt=100, completion=50),
        _run("t1", 1, rounds=40, prompt=200, completion=80, stop="max_rounds",
             max_rounds_bound=True, max_rounds=40),
    )
    eff = cond_domain_efficiency(runs=runs, condition_id=_COND, pricing=_PRICING)
    assert eff.prompt_tokens == 300
    assert eff.completion_tokens == 130
    assert eff.total_tokens == 430
    assert eff.censored_count == 1
    assert eff.cap_bound == 40
    assert eff.max_rounds_hits == 1
    assert eff.rounds_min == 5 and eff.rounds_max == 40
    # cost = (300*1.0 + 130*2.0) / 1e6
    assert eff.cost_usd == (300 * 1.0 + 130 * 2.0) / 1_000_000


def test_tool_call_totals_and_stop_reason_counts_merge():
    runs = (
        _run("t1", 0, rounds=3, prompt=1, completion=1,
             tool_calls={"read_file": 2, "str_replace": 1}),
        _run("t1", 1, rounds=3, prompt=1, completion=1, stop="safety_cap",
             safety_cap_bound=True, safety_cap=60,
             tool_calls={"read_file": 1}),
    )
    eff = cond_domain_efficiency(runs=runs, condition_id=_COND, pricing=_PRICING)
    assert eff.tool_call_totals == {"read_file": 3, "str_replace": 1}
    assert eff.stop_reason_counts == {"completed_natural": 1, "safety_cap": 1}
    assert eff.safety_cap_hits == 1
    assert eff.cap_bound == 60


def test_cost_none_when_condition_not_priced():
    runs = (_run("t1", 0, rounds=1, prompt=1, completion=1),)
    eff = cond_domain_efficiency(
        runs=runs, condition_id="unpriced:model", pricing=_PRICING
    )
    assert eff.cost_usd is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_m1_detail_build.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_eval_lab.reports.m1_detail'`.

- [ ] **Step 3: Write the efficiency builder in `reports/m1_detail.py`**

```python
"""Pure M1 per-domain detail report: build + render, no I/O (mirrors m1.py).

Derives per-task / per-condition pass matrices, grader-aware failure gaps
(evidence_summary), edit signals (edit_paths), task-defect candidates (defects),
fc-v4 classification per task×condition (classify), and a rich per-(condition,
domain) efficiency rollup (CondDomainEfficiency). Every derived value is a pure
function of records + spec + pricing; all iteration is over sorted keys, so the
render is deterministic (byte-identical for fixed input). REPORT-LAYER ONLY: no
runner, no scoring, no pass^k math.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from agent_eval_lab.experiments.pricing import PricingSnapshot, condition_cost_usd
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class CondDomainEfficiency:
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int
    cap_bound: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int
    max_rounds_hits: int
    stop_reason_counts: Mapping[str, int]


def _is_censored(run: RunResult) -> bool:
    return run.trajectory.safety_cap_bound or run.trajectory.max_rounds_bound


def _cap_bound_of(run: RunResult) -> int | None:
    t = run.trajectory
    if t.max_rounds_bound:
        return t.max_rounds
    if t.safety_cap_bound:
        return t.safety_cap
    return None


def _counts(values: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in sorted(values):
        out[v] = out.get(v, 0) + 1
    return out


def cond_domain_efficiency(
    *,
    runs: Sequence[RunResult],
    condition_id: str,
    pricing: PricingSnapshot,
) -> CondDomainEfficiency:
    if not runs:
        return CondDomainEfficiency(
            rounds_median=0.0,
            rounds_min=0,
            rounds_max=0,
            censored_count=0,
            cap_bound=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=None,
            tool_call_totals={},
            safety_cap_hits=0,
            max_rounds_hits=0,
            stop_reason_counts={},
        )
    rounds = [r.trajectory.rounds for r in runs]
    censored = [r for r in runs if _is_censored(r)]
    cap_bound = _cap_bound_of(censored[0]) if censored else None
    prompt = sum(r.trajectory.usage.prompt_tokens for r in runs)
    completion = sum(r.trajectory.usage.completion_tokens for r in runs)
    tool_totals: dict[str, int] = {}
    for r in runs:
        for tool in sorted(r.trajectory.tool_call_counts):
            tool_totals[tool] = tool_totals.get(tool, 0) + r.trajectory.tool_call_counts[
                tool
            ]
    stop_counts = _counts([r.trajectory.stop_reason for r in runs])
    cost = (
        condition_cost_usd(runs, condition_id, pricing)
        if condition_id in pricing.prices
        else None
    )
    return CondDomainEfficiency(
        rounds_median=median(rounds),
        rounds_min=min(rounds),
        rounds_max=max(rounds),
        censored_count=len(censored),
        cap_bound=cap_bound,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cost_usd=cost,
        tool_call_totals=tool_totals,
        safety_cap_hits=stop_counts.get("safety_cap", 0),
        max_rounds_hits=stop_counts.get("max_rounds", 0),
        stop_reason_counts=stop_counts,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_m1_detail_build.py -q`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1_detail.py tests/reports/test_m1_detail_build.py
git commit -m "feat(reports): CondDomainEfficiency builder (censoring-aware, spec §8)"
```

**Verification point:** tokens observed over all runs incl. capped; censored split correct; cost None when unpriced.

---

### Task 5: `reports/m1_detail.py` — `build_m1_detail()` (spec §6)

**Files:**
- Modify: `src/agent_eval_lab/reports/m1_detail.py` (add the detail value objects + `build_m1_detail`)
- Modify: `tests/reports/test_m1_detail_build.py` (add the build-level cases)

Add these value objects to `m1_detail.py`. They hold everything `render_detail` needs (so the renderer is grader-agnostic — spec §5).

```python
@dataclass(frozen=True, kw_only=True)
class TaskConditionCell:
    condition_id: str
    present: bool                 # False -> render "—" row (spec §6: condition missing a task)
    valid_trials: int             # len(valid_runs) for this (task, cond)
    passed_trials: int            # #valid runs with grade.passed
    incomplete: bool              # valid_trials < k (spec §6 void/incomplete; D34)
    per_trial: tuple[bool, ...]   # the ✅❌ string source, record order over valid runs
    dominant_stop_reason: str     # most common stop_reason over valid runs ("—" if none)
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int
    cap_bound: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int
    stop_reason_counts: Mapping[str, int]
    gap: EvidenceGap              # grader-aware gap from a representative failing run (or last run)
    edits: EditPaths              # edit signals from a representative run
    administrative: bool
    invalid_trials: int           # attempts that were not valid (env-masked); spec §6 invalid case
    classifications: tuple[tuple[str, str], ...]  # (category, subcategory) per failing valid run


@dataclass(frozen=True, kw_only=True)
class TaskQuickRef:
    task_id: str
    target_paths: tuple[str, ...]
    grader_id: str
    oracle_total: int | None      # EvidenceGap.oracle_total of a representative run (F only)


@dataclass(frozen=True, kw_only=True)
class TaskDetail:
    task_id: str
    cells: tuple[TaskConditionCell, ...]            # one per condition, sorted by condition_id
    shared_failing_units: tuple[str, ...]           # intersection of failing_units across failing conds
    divergent: bool                                 # True iff the intersection is empty but >1 failing cond


@dataclass(frozen=True, kw_only=True)
class M1Detail:
    domain: str
    conditions_present: tuple[str, ...]
    k: int
    spec_hash: str
    task_quick_refs: tuple[TaskQuickRef, ...]
    tasks: tuple[TaskDetail, ...]
    defect_candidates: tuple[TaskDefectCandidate, ...]
    efficiency: tuple[CondDomainEfficiency, ...]    # one per condition (domain-scoped, sorted)
    efficiency_condition_ids: tuple[str, ...]       # parallel to efficiency, sorted
```

`build_m1_detail(*, domain, outcomes_by_condition, pricing, spec)`:
- `outcomes_by_condition: Mapping[str, Sequence[ReplacementOutcome]]` — the per-condition outcomes FOR THIS DOMAIN (the caller slices `outcomes_by_condition_domain[*][domain]`).
- `conditions_present = tuple(sorted(outcomes_by_condition))`.
- Build a per-(task, condition) view from `ReplacementOutcome`:
  - `valid_runs` (the k-valid subset) → `valid_trials`, `passed_trials`, `per_trial`.
  - `attempts` (the full history) → `invalid_trials = #[a for a in attempts if not a.valid]` (spec §6 invalid/env-masked case; the SiliconFlow 403/429 reads from `ReplacementOutcome.attempts`, glossary `validity mask`).
  - Group `valid_runs` by `run.task_id` (a `ReplacementOutcome` is per task in this harness; group defensively in case of mixed).
- For each task, for each condition:
  - if no records for (task, cond) → `present=False` cell (rest zeroed; spec §6 "condition missing a task entirely: explicit '—' row").
  - `incomplete = valid_trials < spec.k` (spec §6 void/incomplete; D34).
  - efficiency fields from `cond_domain_efficiency(runs=valid_runs_for_this_task_cond, condition_id=cond, pricing=pricing)` (re-callable over a single task's valid runs, spec §8).
  - `dominant_stop_reason`: the max-count stop reason (ties → lexicographically smallest, for determinism); `"—"` if no valid runs.
  - `gap`: `evidence_gap(representative.grade)` where representative = first failing valid run, else first valid run, else (no valid runs) a synthetic gap is not needed since `present=False`.
  - `edits`: `edit_paths(representative.trajectory, target_paths=representative.trajectory.final_state.get("target_paths", ()))` — read `target_paths` from `final_state` (verified at `loop.py:225` + `f_candidate.py`). Guard `final_state is None` → `target_paths=()`.
  - `administrative = gap.administrative`.
  - `classifications = tuple((c.category, c.subcategory or "—") for c in [classify_run(r) for r in valid_runs if not r.grade.passed])` — spec §6.7 fc-v4 per task×condition.
- `shared_failing_units`: intersection of `gap.failing_units` over the **failing** conditions for that task (a condition is "failing" if `passed_trials == 0` and it has valid runs). Empty intersection with >1 failing condition → `divergent=True` (spec §6.5 "divergent failures (no shared unit)"). Single failing condition → its own failing units, `divergent=False`.
- `task_quick_refs`: per task, `target_paths` from a representative run's `final_state`, `grader_id` + `oracle_total` from a representative `EvidenceGap`.
- `defect_candidates`: `task_defect_candidates(tuple(DefectInputGroup(label=cond, runs=valid_runs_for_cond, blocked=False) for cond in conditions_present))` — reuse the shared predicate (spec §6.5 / §4). Use **valid_runs** (the model's real trials) for this domain per condition.
- `efficiency`: per condition, `cond_domain_efficiency(runs=all_valid_runs_for_cond_in_domain, condition_id=cond, pricing=pricing)`; `efficiency_condition_ids` parallel sorted.

- [ ] **Step 1: Write the failing build tests** (append to `tests/reports/test_m1_detail_build.py`)

```python
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.reports.m1_detail import M1Detail, build_m1_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _node_grade(passed, tests, displaced=()):
    return GradeResult(
        grader_id="node_execution", passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"execution": "run", "status": "passed" if passed else "failed",
                  "tests": tests, "displaced_paths": list(displaced)},
    )


def _f_run(task_id, cond, idx, passed, tests, target_paths=("wdio.conf.ts",)):
    return RunResult(
        task_id=task_id, condition_id=cond, run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=idx, stop_reason="completed_natural", rounds=4,
            final_state={"files": {}, "target_paths": list(target_paths)},
        ),
        grade=_node_grade(passed, tests),
    )


def _outcome(runs, *, invalid=0, void=False):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    ) + tuple(
        TrialAttempt(attempt_index=len(runs) + j, valid=False, run=runs[0])
        for j in range(invalid)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=void)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def test_build_detail_per_task_pass_contribution():
    cond = _COND
    runs = [
        _f_run("f1", cond, i, passed=(i == 0),
               tests=[["a", "passed" if i == 0 else "failed"]])
        for i in range(3)
    ]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond: (_outcome(runs),)},
        pricing=_PRICING,
        spec=_spec(),
    )
    assert isinstance(detail, M1Detail)
    cell = detail.tasks[0].cells[0]
    assert cell.valid_trials == 3
    assert cell.passed_trials == 1
    assert cell.per_trial == (True, False, False)


def test_shared_failing_unit_intersection():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, i, passed=False,
                     tests=[["a", "failed"], ["b", "passed"]]) for i in range(2)]
    runs_b = [_f_run("f1", cond_b, i, passed=False,
                     tests=[["a", "failed"], ["b", "failed"]]) for i in range(2)]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond_a: (_outcome(runs_a),),
                               cond_b: (_outcome(runs_b),)},
        pricing=_PRICING, spec=_spec(),
    )
    # both conditions fail "a" -> shared; only b fails "b" -> not shared.
    assert detail.tasks[0].shared_failing_units == ("a",)
    assert detail.tasks[0].divergent is False


def test_divergent_when_no_shared_unit():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f1", cond_b, 0, passed=False, tests=[["b", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond_a: (_outcome(runs_a),),
                               cond_b: (_outcome(runs_b),)},
        pricing=_PRICING, spec=_spec(),
    )
    assert detail.tasks[0].shared_failing_units == ()
    assert detail.tasks[0].divergent is True


def test_invalid_trials_counted_from_attempts():
    cond = _COND
    runs = [_f_run("f1", cond, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond: (_outcome(runs, invalid=2),)},
        pricing=_PRICING, spec=_spec(),
    )
    assert detail.tasks[0].cells[0].invalid_trials == 2


def test_condition_missing_task_is_absent_cell():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f2", cond_b, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond_a: (_outcome(runs_a),),
                               cond_b: (_outcome(runs_b),)},
        pricing=_PRICING, spec=_spec(),
    )
    f1 = next(t for t in detail.tasks if t.task_id == "f1")
    cell_b = next(c for c in f1.cells if c.condition_id == cond_b)
    assert cell_b.present is False


def test_defect_candidate_flagged_when_all_conditions_fail():
    cond_a, cond_b = "a:m", "b:m"
    runs_a = [_f_run("f1", cond_a, 0, passed=False, tests=[["a", "failed"]])]
    runs_b = [_f_run("f1", cond_b, 0, passed=False, tests=[["a", "failed"]])]
    detail = build_m1_detail(
        domain="F",
        outcomes_by_condition={cond_a: (_outcome(runs_a),),
                               cond_b: (_outcome(runs_b),)},
        pricing=_PRICING, spec=_spec(),
    )
    assert [c.task_id for c in detail.defect_candidates] == ["f1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_m1_detail_build.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_m1_detail'` (the efficiency tests still pass).

- [ ] **Step 3: Implement the value objects + `build_m1_detail` in `reports/m1_detail.py`**

Add the imports at the top of `m1_detail.py`:

```python
from agent_eval_lab.experiments.schema import ExperimentSpec
from agent_eval_lab.reports.classify import classify_run
from agent_eval_lab.reports.defects import (
    DefectInputGroup,
    TaskDefectCandidate,
    task_defect_candidates,
)
from agent_eval_lab.reports.edit_paths import EditPaths, edit_paths
from agent_eval_lab.reports.evidence_summary import EvidenceGap, evidence_gap
from agent_eval_lab.runners.multi_run import ReplacementOutcome
```

Add the value objects shown above, then:

```python
def _dominant_stop_reason(runs: Sequence[RunResult]) -> str:
    counts = _counts([r.trajectory.stop_reason for r in runs])
    if not counts:
        return "—"
    # max count, ties broken lexicographically (counts is already sorted-key)
    return max(counts, key=lambda sr: (counts[sr], [-ord(ch) for ch in sr]))


def _representative(runs: Sequence[RunResult]) -> RunResult:
    """First failing valid run, else the first valid run (deterministic)."""
    return next((r for r in runs if not r.grade.passed), runs[0])


def _target_paths_of(run: RunResult) -> tuple[str, ...]:
    fs = run.trajectory.final_state
    if fs is None:
        return ()
    return tuple(fs.get("target_paths", ()))


def _cell(condition_id: str, runs: Sequence[RunResult], k: int,
          invalid: int, pricing: PricingSnapshot) -> TaskConditionCell:
    if not runs:
        return TaskConditionCell(
            condition_id=condition_id, present=False, valid_trials=0,
            passed_trials=0, incomplete=True, per_trial=(),
            dominant_stop_reason="—", rounds_median=0.0, rounds_min=0, rounds_max=0,
            censored_count=0, cap_bound=None, prompt_tokens=0, completion_tokens=0,
            total_tokens=0, cost_usd=None, tool_call_totals={}, safety_cap_hits=0,
            stop_reason_counts={},
            gap=EvidenceGap(grader_id="—", oracle_total=None, oracle_passed=None,
                            failing_units=(), displaced_paths=(),
                            administrative=False, status="incomplete"),
            edits=EditPaths(edited=(), out_of_scope=()),
            administrative=False, invalid_trials=invalid, classifications=(),
        )
    eff = cond_domain_efficiency(runs=runs, condition_id=condition_id, pricing=pricing)
    rep = _representative(runs)
    gap = evidence_gap(rep.grade)
    edits = edit_paths(rep.trajectory, target_paths=_target_paths_of(rep))
    classifications = tuple(
        (c.category, c.subcategory or "—")
        for c in (classify_run(r) for r in runs if not r.grade.passed)
    )
    return TaskConditionCell(
        condition_id=condition_id, present=True, valid_trials=len(runs),
        passed_trials=sum(1 for r in runs if r.grade.passed),
        incomplete=len(runs) < k,
        per_trial=tuple(r.grade.passed for r in runs),
        dominant_stop_reason=_dominant_stop_reason(runs),
        rounds_median=eff.rounds_median, rounds_min=eff.rounds_min,
        rounds_max=eff.rounds_max, censored_count=eff.censored_count,
        cap_bound=eff.cap_bound, prompt_tokens=eff.prompt_tokens,
        completion_tokens=eff.completion_tokens, total_tokens=eff.total_tokens,
        cost_usd=eff.cost_usd, tool_call_totals=eff.tool_call_totals,
        safety_cap_hits=eff.safety_cap_hits, stop_reason_counts=eff.stop_reason_counts,
        gap=gap, edits=edits, administrative=gap.administrative,
        invalid_trials=invalid, classifications=classifications,
    )


def build_m1_detail(
    *,
    domain: str,
    outcomes_by_condition: Mapping[str, Sequence[ReplacementOutcome]],
    pricing: PricingSnapshot,
    spec: ExperimentSpec,
) -> M1Detail:
    conditions_present = tuple(sorted(outcomes_by_condition))
    # (task_id, cond) -> (valid_runs, invalid_count)
    by_task_cond: dict[str, dict[str, tuple[list[RunResult], int]]] = {}
    valid_by_cond: dict[str, list[RunResult]] = {c: [] for c in conditions_present}
    for cond in conditions_present:
        for outcome in outcomes_by_condition[cond]:
            invalid = sum(1 for a in outcome.attempts if not a.valid)
            for run in outcome.valid_runs:
                slot = by_task_cond.setdefault(run.task_id, {}).setdefault(
                    cond, ([], 0)
                )
                slot[0].append(run)
                valid_by_cond[cond].append(run)
            # attribute invalid attempts to the outcome's task (first valid run's
            # task_id, or skip if a fully-void outcome has no valid runs).
            if outcome.valid_runs:
                tid = outcome.valid_runs[0].task_id
                runs_list, _ = by_task_cond[tid][cond]
                by_task_cond[tid][cond] = (runs_list, invalid)

    tasks: list[TaskDetail] = []
    quick: list[TaskQuickRef] = []
    for task_id in sorted(by_task_cond):
        cells = tuple(
            _cell(
                cond,
                by_task_cond[task_id].get(cond, ([], 0))[0],
                spec.k,
                by_task_cond[task_id].get(cond, ([], 0))[1],
                pricing,
            )
            for cond in conditions_present
        )
        failing_cells = [
            c for c in cells if c.present and c.passed_trials == 0 and c.valid_trials
        ]
        failing_unit_sets = [set(c.gap.failing_units) for c in failing_cells]
        if failing_unit_sets:
            shared = set.intersection(*failing_unit_sets)
        else:
            shared = set()
        divergent = len(failing_cells) > 1 and not shared
        tasks.append(
            TaskDetail(
                task_id=task_id,
                cells=cells,
                shared_failing_units=tuple(sorted(shared)),
                divergent=divergent,
            )
        )
        rep_cell = next((c for c in cells if c.present), cells[0])
        target_paths = ()
        rep_runs = by_task_cond[task_id].get(
            rep_cell.condition_id, ([], 0)
        )[0]
        if rep_runs:
            target_paths = _target_paths_of(_representative(rep_runs))
        quick.append(
            TaskQuickRef(
                task_id=task_id,
                target_paths=tuple(target_paths),
                grader_id=rep_cell.gap.grader_id,
                oracle_total=rep_cell.gap.oracle_total,
            )
        )

    defect_candidates = task_defect_candidates(
        tuple(
            DefectInputGroup(label=cond, runs=tuple(valid_by_cond[cond]), blocked=False)
            for cond in conditions_present
        )
    )
    efficiency = tuple(
        cond_domain_efficiency(
            runs=tuple(valid_by_cond[cond]), condition_id=cond, pricing=pricing
        )
        for cond in conditions_present
    )
    return M1Detail(
        domain=domain,
        conditions_present=conditions_present,
        k=spec.k,
        spec_hash=spec.spec_hash,
        task_quick_refs=tuple(quick),
        tasks=tuple(tasks),
        defect_candidates=defect_candidates,
        efficiency=efficiency,
        efficiency_condition_ids=conditions_present,
    )
```

> The `_dominant_stop_reason` tiebreak: `counts` is built over a sorted list so equal-count keys are visited in ascending order; `max` with a key of `(count, <descending-char proxy>)` returns the lexicographically smallest among ties. If this proves fiddly, simplify the key to `(counts[sr], tuple(-ord(c) for c in sr))` (the version shown) — both are deterministic; the test asserts a single-reason case so either passes, but keep the deterministic tiebreak for the multi-reason render.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_m1_detail_build.py -q`
Expected: PASS (all efficiency + build cases).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1_detail.py tests/reports/test_m1_detail_build.py
git commit -m "feat(reports): build_m1_detail per-domain detail (gaps, edits, defects, fc-v4)"
```

**Verification point:** pass matrix, shared/divergent intersection, invalid-from-attempts, absent cell, and defect reuse all green.

---

### Task 6: `reports/m1_detail.py` — `render_detail()` (spec §6 sections)

**Files:**
- Modify: `src/agent_eval_lab/reports/m1_detail.py` (add `render_detail`)
- Create: `tests/reports/test_m1_detail_render.py`

`render_detail(detail: M1Detail) -> str` emits the §6 sections in order, all from `M1Detail` (renderer is grader-agnostic). Section labels (must appear verbatim for the render test):
1. Header: `# M1 subreport — {domain}` + a line with conditions, `k`, task count, `spec_hash`.
2. `## Task quick-reference` — table: `task | target_paths | grader | oracle tests`.
3. `## Cross-model summary` — task × condition matrix: `pass^k contribution (passed/valid)` + per-trial `✅❌` string + dominant stop_reason.
4. `## Per-task detail` — per task, per condition block: pass matrix, rounds `median [min–max]` with **censoring annotation** when `censored_count > 0` (e.g. `16 (2/5 right-censored at cap 20)`), tokens (prompt/completion/total), `cost_usd`, tool-call counts, safety-cap hits, stop-reason; grader-aware gap (F → `passed X/Y oracle tests; failing: …`; D → `missing_required` / `present_forbidden`); edit signals (`edited`, of which `out-of-scope` — labeled distinct from `displaced_paths`).
   - **Administrative label** (spec §6 edge): when `cell.administrative` → render `administrative 0/k — not executed (owner decision)`, NEVER a 0-round/0-token failure.
   - **Incomplete** cell → `status = incomplete`, flagged, excluded from pass^k framing.
   - **Absent** cell (`present=False`) → explicit `—` row.
   - **Invalid** trials → `invalid_trials` shown separately, labeled as env-masked (not a model gap).
5. `## Task-defect candidates` — table; below each flag, the shared failing oracle unit(s) (`detail.tasks[*].shared_failing_units`) or `divergent failures (no shared unit)`. Flagged "for human review, never auto-classified".
6. `## Per-condition efficiency` — one row per condition, same columns as the overview rollup (rounds median [min–max] with censoring mark, prompt/completion/total tok, cost_usd, total tool calls, safety-cap hits, max-rounds hits, dominant stop_reason).
7. `## Failure classification (fc-v4) per task × condition` — from `cell.classifications`.

Use `✅`/`❌` for the per-trial string. Use `—` for None/empty cells. Build a shared `_rounds_cell(median, lo, hi, censored, cap)` helper:

```python
def _rounds_cell(median, lo, hi, censored, cap):
    base = f"{median:g} [{lo}–{hi}]"
    if censored > 0:
        bound = "cap" if cap is None else f"cap {cap}"
        base += f" ({censored} right-censored at {bound})"
    return base
```

- [ ] **Step 1: Write the failing render test** (`tests/reports/test_m1_detail_render.py`)

```python
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_COND = "deepseek:deepseek-v4-pro"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={_COND: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0)},
)


def _node_grade(passed, tests, **extra):
    ev = {"execution": "run", "status": "passed" if passed else "failed",
          "tests": tests, "displaced_paths": []}
    ev.update(extra)
    return GradeResult(grader_id="node_execution", passed=passed,
                       score=1.0 if passed else 0.0, evidence=ev)


def _f_run(idx, passed, tests, *, stop="completed_natural",
           safety_cap_bound=False, max_rounds=None, rounds=4):
    return RunResult(
        task_id="f1", condition_id=_COND, run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=idx, stop_reason=stop, rounds=rounds,
            safety_cap_bound=safety_cap_bound, max_rounds=max_rounds,
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=_node_grade(passed, tests),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=False)


def _spec():
    return freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )


def _render(runs):
    detail = build_m1_detail(
        domain="F", outcomes_by_condition={_COND: (_outcome(runs),)},
        pricing=_PRICING, spec=_spec(),
    )
    return render_detail(detail)


def test_render_has_all_sections():
    md = _render([_f_run(i, passed=False, tests=[["a", "failed"]]) for i in range(3)])
    assert "# M1 subreport — F" in md
    assert "## Task quick-reference" in md
    assert "## Cross-model summary" in md
    assert "## Per-task detail" in md
    assert "## Task-defect candidates" in md
    assert "## Per-condition efficiency" in md
    assert "## Failure classification (fc-v4) per task × condition" in md


def test_render_per_trial_string_and_gap():
    md = _render([
        _f_run(0, passed=True, tests=[["a", "passed"], ["b", "passed"]]),
        _f_run(1, passed=False, tests=[["a", "passed"], ["b", "failed"]]),
    ])
    assert "✅" in md and "❌" in md
    # grader-aware gap names the failing oracle test
    assert "b" in md


def test_render_censoring_annotation():
    md = _render([
        _f_run(0, passed=False, tests=[["a", "failed"]]),
        _f_run(1, passed=False, tests=[["a", "failed"]],
               stop="max_rounds", max_rounds=40, rounds=40),
    ])
    # the censored run must annotate the rounds cell, never silently
    assert "right-censored" in md
    assert "cap 40" in md


def test_render_administrative_label():
    admin = RunResult(
        task_id="f1", condition_id=_COND, run_index=0,
        trajectory=Trajectory(
            turns=(), usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0, stop_reason="completed_natural", rounds=0,
            final_state={"files": {}, "target_paths": []},
        ),
        grade=GradeResult(grader_id="node_execution", passed=False, score=0.0,
                          evidence={"marked_failed_not_executed": True}),
    )
    md = _render([admin])
    assert "administrative" in md
    assert "not executed" in md
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/reports/test_m1_detail_render.py -q`
Expected: FAIL — `ImportError: cannot import name 'render_detail'`.

- [ ] **Step 3: Implement `render_detail` in `reports/m1_detail.py`**

Write `render_detail(detail)` and its section helpers (`_header_lines`, `_quickref_lines`, `_summary_lines`, `_per_task_lines`, `_defect_lines`, `_efficiency_lines`, `_classification_lines`) following the `m1.py`/`final.py` line-list pattern (each helper returns `list[str]`, joined `"\n".join(lines) + "\n"`). Key rules to encode:

```python
def _per_trial_str(per_trial: tuple[bool, ...]) -> str:
    return "".join("✅" if p else "❌" for p in per_trial) or "—"


def _rounds_cell(median: float, lo: int, hi: int, censored: int,
                 cap: int | None) -> str:
    base = f"{median:g} [{lo}–{hi}]"
    if censored > 0:
        bound = "cap" if cap is None else f"cap {cap}"
        base += f" ({censored} right-censored at {bound})"
    return base


def _gap_phrase(gap) -> str:
    if gap.administrative:
        return "administrative — not executed (owner decision)"
    if gap.status == "no_answer":
        return "no answer (no assistant message)"
    if gap.oracle_total is not None:
        failing = ", ".join(f"`{u}`" for u in gap.failing_units) or "none"
        return f"passed {gap.oracle_passed}/{gap.oracle_total} oracle tests; failing: {failing}"
    if gap.failing_units:
        return "missed/forbidden facts: " + ", ".join(f"`{u}`" for u in gap.failing_units)
    return gap.status
```

The per-task block must, per cell:
- absent (`present is False`) → emit a `—` row.
- administrative (`cell.administrative`) → emit `administrative 0/{k} — not executed (owner decision)`, NEVER tokens/rounds as a failure.
- incomplete (`cell.incomplete` and not administrative) → label `status = incomplete (excluded from pass^k)`.
- else → the full block: pass `passed_trials/valid_trials` + `_per_trial_str`, `_rounds_cell(...)`, tokens `prompt / completion / total`, `cost_usd` (`—` if None), tool calls, `safety_cap_hits`, dominant stop reason; `_gap_phrase(cell.gap)`; edit signals: `edited: …; out-of-scope: …; displaced (oracle overlay): …` (the last from `cell.gap.displaced_paths`, labeled distinct).
- invalid: when `cell.invalid_trials > 0`, append `invalid (env-masked) trials: {n} — excluded, not a model gap`.

The defect section lists each `detail.defect_candidates`, and under each, the matching `TaskDetail.shared_failing_units` (or `divergent failures (no shared unit)` when `divergent`).

The efficiency section iterates `zip(detail.efficiency_condition_ids, detail.efficiency)`.

The classification section iterates tasks → cells → `cell.classifications`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/reports/test_m1_detail_render.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1_detail.py tests/reports/test_m1_detail_render.py
git commit -m "feat(reports): render_detail M1 subreport markdown (spec §6 sections)"
```

**Verification point:** all 7 sections present; per-trial ✅❌ string; censoring annotation; administrative label; gap phrasing.

---

### Task 7: `reports/m1_detail.py` — determinism (byte-identical)

**Files:**
- Create: `tests/reports/test_m1_detail_determinism.py`

Mirrors `tests/experiments/test_m1_determinism.py`: build+render twice over a multi-condition, multi-task input and assert byte-identical.

- [ ] **Step 1: Write the determinism test** (`tests/reports/test_m1_detail_determinism.py`)

```python
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.pricing import PricePoint, PricingSnapshot
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

_A, _B = "a:m1", "b:m2"
_PRICING = PricingSnapshot(
    snapshot_date="2026-06-13",
    prices={
        _A: PricePoint(input_per_mtok=1.0, output_per_mtok=2.0),
        _B: PricePoint(input_per_mtok=0.5, output_per_mtok=1.0),
    },
)


def _run(task_id, cond, idx, passed, tests):
    return RunResult(
        task_id=task_id, condition_id=cond, run_index=idx,
        trajectory=Trajectory(
            turns=(
                ToolCallTurn(tool_calls=(
                    ToolCall(name="str_replace", arguments={"path": "wdio.conf.ts"}),
                    ToolCall(name="write_file", arguments={"path": "extra.ts",
                                                           "content": "x"}),
                )),
                MessageTurn(role="assistant", content="done"),
            ),
            usage=Usage(prompt_tokens=100 + idx, completion_tokens=50, latency_s=1.0),
            run_index=idx, stop_reason="completed_natural", rounds=4 + idx,
            tool_call_counts={"str_replace": 1, "write_file": 1, "read_file": 2},
            final_state={"files": {}, "target_paths": ["wdio.conf.ts"]},
        ),
        grade=GradeResult(
            grader_id="node_execution", passed=passed,
            score=1.0 if passed else 0.0,
            evidence={"execution": "run", "status": "passed" if passed else "failed",
                      "tests": tests, "displaced_paths": []},
        ),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=tuple(runs), attempts=attempts, void=False)


def test_build_render_byte_identical():
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    outcomes = {
        _A: (
            _outcome([_run("f1", _A, i, i == 0, [["a", "passed" if i == 0 else
                                                  "failed"]]) for i in range(3)]),
            _outcome([_run("f2", _A, i, False, [["b", "failed"]]) for i in range(3)]),
        ),
        _B: (
            _outcome([_run("f1", _B, i, False, [["a", "failed"]]) for i in range(3)]),
            _outcome([_run("f2", _B, i, False, [["b", "failed"]]) for i in range(3)]),
        ),
    }
    kw = dict(domain="F", outcomes_by_condition=outcomes, pricing=_PRICING, spec=spec)
    md1 = render_detail(build_m1_detail(**kw))
    md2 = render_detail(build_m1_detail(**kw))
    assert md1 == md2
```

- [ ] **Step 2: Run test to verify it passes** (implementation already exists from Tasks 4-6)

Run: `uv run pytest tests/reports/test_m1_detail_determinism.py -q`
Expected: PASS. If it FAILS, the cause is non-deterministic iteration (an unsorted `set`/`dict` walk) — fix by sorting the offending key iteration in `m1_detail.py`, then re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/reports/test_m1_detail_determinism.py
git commit -m "test(reports): M1 subreport determinism (byte-identical render)"
```

**Verification point:** two builds render byte-identical (proves all iteration is over sorted keys, spec §4 determinism).

---

### Task 8: `m1.py` overview additions + heading rename (spec §7) + `test_m1_render.py` update

**Files:**
- Modify: `src/agent_eval_lab/reports/m1.py` (heading rename `m1.py:374`; new efficiency rollup; per-domain headlines; subreport links)
- Modify: `tests/reports/test_m1_render.py` (heading assertion line 70; new rollup + link assertions)

The overview reuses the new `CondDomainEfficiency` for its rollup so the overview and subreport agree. `build_m1_report` already receives `outcomes_by_condition_domain`; thread a per-(condition, domain) `CondDomainEfficiency` through a new `M1Report` field plus the subreport filenames.

- [ ] **Step 1: Write/extend the failing tests** (`tests/reports/test_m1_render.py`)

Update line 70 from:

```python
    assert "fc-v4" in md or "Failure taxonomy" in md
```

to:

```python
    assert "Failure classification (fc-v4) per condition" in md
    assert "Failure taxonomy" not in md
```

Add two new tests at the end of the file:

```python
def test_render_has_efficiency_and_cost_rollup():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "Efficiency & cost" in md
    # rollup columns
    assert "rounds" in md.lower() and "cost" in md.lower()


def test_render_has_subreport_links_and_headline():
    cond = "deepseek:deepseek-v4-pro"
    outcomes = {cond: {"D": (_outcome("t0", cond, [True] * 5),)}}
    _, md = _report(outcomes)
    assert "Subreports" in md
    assert "M1-D-report.md" in md
    # deterministic per-domain headline
    assert "best pass^k" in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/reports/test_m1_render.py -q`
Expected: FAIL — heading assertion fails (old "Failure taxonomy" heading still present) and the new rollup/link/headline assertions fail.

- [ ] **Step 3: Implement the overview additions in `m1.py`**

a. **Heading rename** (`m1.py:374`):

```python
    lines = [
        f"## Failure classification ({report.classifier_version}) per condition",
        "",
    ]
```

b. **Add a new `CondDomainEfficiency` rollup field + subreport list to `M1Report`.** Import the builder and value object at the top of `m1.py`:

```python
from agent_eval_lab.reports.m1_detail import (
    CondDomainEfficiency,
    cond_domain_efficiency,
)
```

Add to `M1Report` (after `efficiency`):

```python
    cond_domain_efficiency_rollup: tuple[tuple[str, str, CondDomainEfficiency], ...]
    subreport_domains: tuple[str, ...]
```

(`(condition_id, domain, CondDomainEfficiency)` triples, sorted; `subreport_domains` = sorted domains with runs, drives the §7 Subreports links.)

c. In `build_m1_report`, while iterating conditions/domains (the loop already computes `valid = _valid_runs(outcomes)` at `m1.py:167`), also accumulate:

```python
            rollup.append(
                (cond, domain, cond_domain_efficiency(
                    runs=valid, condition_id=cond, pricing=pricing
                ))
            )
```

(initialize `rollup: list[tuple[str, str, CondDomainEfficiency]] = []` near the other accumulators, and pass `cond_domain_efficiency_rollup=tuple(rollup)`, `subreport_domains=tuple(sorted(domains_seen))` into the `M1Report(...)` constructor.)

d. **New renderer sections.** Add `_efficiency_rollup_lines`, `_headline_lines`, and `_subreport_lines`, and insert them into `render_markdown` (after `_per_domain_lines`, before `_pareto_lines` for the rollup; headlines near the per-domain section; subreports near the end):

```python
def _efficiency_rollup_lines(report: M1Report) -> list[str]:
    lines = [
        "## Efficiency & cost",
        "",
        "Per (condition, domain). Rounds are time-to-completion (right-censored "
        "for budget-capped runs); tokens and cost are observed over ALL valid "
        "runs incl. capped (never censored).",
        "",
        "| condition | domain | rounds median [min–max] | prompt tok | "
        "completion tok | total tok | cost (USD) | tool calls | safety-cap hits "
        "| max-rounds hits | dominant stop |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cond, domain, eff in report.cond_domain_efficiency_rollup:
        rounds = f"{eff.rounds_median:g} [{eff.rounds_min}–{eff.rounds_max}]"
        if eff.censored_count > 0:
            bound = "cap" if eff.cap_bound is None else f"cap {eff.cap_bound}"
            rounds += f" ({eff.censored_count} right-censored at {bound})"
        cost = "—" if eff.cost_usd is None else f"{eff.cost_usd:.4f}"
        total_tools = sum(eff.tool_call_totals.values())
        dominant = (
            max(
                eff.stop_reason_counts,
                key=lambda sr: (eff.stop_reason_counts[sr], sr),
            )
            if eff.stop_reason_counts
            else "—"
        )
        lines.append(
            f"| {cond} | {domain} | {rounds} | {eff.prompt_tokens} "
            f"| {eff.completion_tokens} | {eff.total_tokens} | {cost} "
            f"| {total_tools} | {eff.safety_cap_hits} | {eff.max_rounds_hits} "
            f"| {dominant} |"
        )
    return lines + [""]


def _headline_lines(report: M1Report) -> list[str]:
    lines = ["## Per-domain headlines", ""]
    domains = sorted({r.domain for r in report.per_domain_results})
    for domain in domains:
        rows = [r for r in report.per_domain_results if r.domain == domain]
        best = max(rows, key=lambda r: (r.estimate, ))
        cheapest = None
        frontier_cost = None
        for chart in report.pareto_charts:
            if chart.domain == domain and chart.axis == "cost_usd":
                for p in chart.frontier:
                    if frontier_cost is None or p.cost < frontier_cost:
                        frontier_cost, cheapest = p.cost, p.condition_id
        cheap_txt = cheapest or "—"
        lines.append(
            f"- **{domain}** — best pass^k: `{best.condition_id}` "
            f"({best.estimate:.3f}); cheapest on cost-frontier: `{cheap_txt}`"
        )
    return lines + [""]


def _subreport_lines(report: M1Report) -> list[str]:
    lines = ["## Subreports", ""]
    for domain in report.subreport_domains:
        lines.append(f"- [`M1-{domain}-report.md`](M1-{domain}-report.md)")
    # Hand-authored companions (never generated, never overwritten — spec §2/§7)
    lines += [
        "- [`M1-F-failure-analysis.md`](M1-F-failure-analysis.md) "
        "(hand-authored companion)",
        "- [`M1-F-report-NOTES.md`](M1-F-report-NOTES.md) (hand-authored companion)",
    ]
    return lines + [""]
```

Then in `render_markdown`, update the section list:

```python
def render_markdown(report: M1Report) -> str:
    lines = (
        _header_lines(report)
        + _per_domain_lines(report)
        + _headline_lines(report)
        + _composite_lines(report)
        + _efficiency_rollup_lines(report)
        + _pareto_lines(report)
        + _comparison_lines(report)
        + _taxonomy_lines(report)
        + _validity_lines(report)
        + _subreport_lines(report)
    )
    return "\n".join(lines) + "\n"
```

> The existing per-domain, composite, Pareto, comparison, validity sections render byte-for-byte as today (spec §7: "Everything else stays byte-for-byte"). Only NEW sections are inserted and the taxonomy heading text changes. The existing `test_m1_render.py` tests for those sections must continue to pass.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/reports/test_m1_render.py tests/reports/test_m1_build.py tests/experiments/test_m1_determinism.py -q`
Expected: PASS. The determinism test for the overview must still pass (the new sections are deterministic). If `test_m1_build.py` asserts the `M1Report` field set, update its construction expectations to include the two new fields.

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/reports/m1.py tests/reports/test_m1_render.py
git commit -m "feat(reports): M1 overview efficiency rollup + headlines + subreport links; rename heading"
```

**Verification point:** heading is "Failure classification (fc-v4) per condition"; "Failure taxonomy" gone; rollup + Subreports + headline present; existing overview sections unchanged + determinism green.

---

### Task 9: `cli.py` `report-m1` wiring (spec §9)

**Files:**
- Modify: `src/agent_eval_lab/cli.py` — `report-m1` argparse (`cli.py:1558-1575`) and `_run_report_m1` (`cli.py:1172-1200`).

Add `--subreports/--no-subreports` (default on) + `--subreport-dir`; after writing the overview, for each domain present write `M1-<domain>-report.md` into the same dir as `--out` (or `--subreport-dir` if given).

- [ ] **Step 1: Add the argparse flags** (`cli.py`, after `cli.py:1575`)

```python
    rm.add_argument(
        "--subreports",
        dest="subreports",
        action="store_true",
        default=True,
        help="also write per-domain M1-<domain>-report.md subreports (default on)",
    )
    rm.add_argument(
        "--no-subreports",
        dest="subreports",
        action="store_false",
        help="suppress per-domain subreports",
    )
    rm.add_argument(
        "--subreport-dir",
        type=Path,
        default=None,
        help="directory for subreports (default: same dir as --out)",
    )
```

- [ ] **Step 2: Add the imports for the detail builder/renderer** (near `cli.py:51-52`)

```python
from agent_eval_lab.reports.m1_detail import build_m1_detail, render_detail
```

- [ ] **Step 3: Extend `_run_report_m1` to write subreports** (after `_atomic_write(args.out, render_m1(report))` at `cli.py:1198`)

```python
    if args.subreports:
        out_dir = args.subreport_dir or args.out.parent
        for domain in report.subreport_domains:
            outcomes_for_domain = {
                cond: outcomes[cond][domain]
                for cond in sorted(outcomes)
                if domain in outcomes[cond]
            }
            detail = build_m1_detail(
                domain=domain,
                outcomes_by_condition=outcomes_for_domain,
                pricing=pricing,
                spec=spec,
            )
            subreport_path = out_dir / f"M1-{domain}-report.md"
            _atomic_write(subreport_path, render_detail(detail))
            print(subreport_path)
```

> `report.subreport_domains` was added to `M1Report` in Task 8, so the subreport set and the overview's "Subreports" links are computed from the same source (spec §9: "links and files never drift").

- [ ] **Step 4: Smoke-test the CLI end-to-end**

There is no committed multi-condition multi-domain fixture for a CLI integration test, and the spec mandates no new run artifacts. Verify via a manual smoke run against the existing F artifacts if present, otherwise rely on the unit tests of `build_m1_detail`/`render_detail`. Run the existing CLI tests to confirm no regression:

Run: `uv run pytest tests/ -k "report_m1 or cli" -q`
Expected: PASS (no regression in CLI dispatch / argparse).

- [ ] **Step 5: Commit**

```bash
git add src/agent_eval_lab/cli.py
git commit -m "feat(cli): report-m1 writes per-domain subreports beside --out (spec §9)"
```

**Verification point:** `--subreports` default on; subreports land in `--out`'s dir (or `--subreport-dir`); domain set matches the overview links.

---

### Task 10: Full-suite + lint/format verification

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest`
Expected: PASS — all tests green, including the untouched `tests/reports/test_final.py` (the `defects.py` refactor net), `tests/experiments/test_m1_determinism.py`, and the new `test_evidence_summary.py` / `test_edit_paths.py` / `test_defects.py` / `test_m1_detail_build.py` / `test_m1_detail_render.py` / `test_m1_detail_determinism.py`.

- [ ] **Step 2: Lint**

Run: `uv run ruff check src tests`
Expected: no errors. Fix any `E`/`F`/`I`/`UP` findings (line-length 88, import sorting).

- [ ] **Step 3: Format check**

Run: `uv run ruff format --check src tests`
Expected: clean. If it reports files, run `uv run ruff format src tests` and re-run the test suite, then commit.

- [ ] **Step 4: Final commit (if format/lint changed anything)**

```bash
git add -A
git commit -m "chore(reports): ruff format + lint clean for M1 report enhancement"
```

**Verification point:** `uv run pytest` fully green; `ruff check` and `ruff format --check` clean.

---

## Self-Review (against the spec)

**Spec coverage:**
- §4 separation of `evidence_gap`(GradeResult) vs `edit_paths`(Trajectory) → Tasks 2 & 3, enforced as separate modules; scope-boundary note up top.
- §5 `EvidenceGap` + grade-only contract + degraded branch + unknown-grader totality → Task 2.
- §5a `EditPaths` + out-of-scope + unknown-tool fail-quiet → Task 3.
- §6 subreport content (header, quick-ref, cross-model summary, per-task detail, defect candidates + shared failing units, efficiency, fc-v4 per task×condition) + edge cases (void/incomplete, administrative, invalid, condition-missing-task) → Tasks 5 & 6.
- §7 overview additions (efficiency rollup, subreport links, per-domain headline, heading rename) → Task 8.
- §8 `CondDomainEfficiency` (new value object, not extending `EfficiencySummary`) + censoring discipline + cost reuse → Task 4.
- §9 CLI flags + subreports beside `--out` → Task 9.
- §10 TDD test files → all created, tests-first in every task.
- §11 out-of-scope honored → scope-boundary note; the only existing-module change is the pure `final.py` extract-and-import (Task 1), guarded by its tests.

**Reconciliation notes (field names that differed from the spec's prose):**
- `marked_failed_not_executed` — **not present in any `src/` code or committed artifact** (only in `docs/`); it is a forward-declared hypothetical key. Handled with a defensive `grade.evidence.get("marked_failed_not_executed", False)` so the adapter is correct whether or not a producer ever emits it. (See "Verified source facts".)
- spec §3 says `trajectory.usage{…latency_s}`; the existing efficiency uses `trajectory.wall_time_s` for medians, and §8's column list carries no latency field — so no latency/wall-time column is added.
- `condition_cost_usd` is **positional**, not kw-only (`pricing.py:67`) — call sites use positional args.
- The hand-companion files (`M1-F-failure-analysis.md`, `M1-F-report-NOTES.md`) and `reports/v1-archive/overview.md` referenced by the spec **do not yet exist** in the repo; they are the aspirational bar/companions. The overview links to them unconditionally per spec §7 (the generator never produces them; it only links). This is correct: spec §2/§7 say the generator coexists with and links to hand companions, never clobbers them.

**Judgment calls (cite section):**
- §6.4 "representative run" for a cell's `gap`/`edits`: the spec does not name which run supplies the per-cell gap/edit display when k>1. Chose deterministically: first failing valid run, else first valid run. Documented in Task 5.
- §6.3 "dominant stop_reason": tie-break is unspecified; chose lexicographically-smallest-among-max-count for determinism (Task 5/8).
- §9 CLI integration test: no committed multi-domain fixture and spec §11 forbids new run artifacts, so end-to-end CLI coverage relies on the `build_m1_detail`/`render_detail` unit + determinism tests plus a no-regression CLI run (Task 9 Step 4).
