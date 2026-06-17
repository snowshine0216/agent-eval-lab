# B-1 Live Spike Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build (code + tests + runbook, no live execution) the B-1 MicroStrategy Library browser-automation spike: a standalone `run-b` driver that drives each candidate model live, records a grade-less `BTrial`, emits a verdict sheet for human review, and a pure `report-b` that joins owner verdicts with trials to produce `pass_at_1` + efficiency + skill-delta.

**Architecture:** Three phases (§3.1 of the spec). Phase 1 (`run-b`, edge): the candidate builds the object, the runner records a grade-less `BTrial` and emits a verdict sheet. Phase 2 (owner, manual, NOT built): owner validates each saved object against the definition-match checklist. Phase 3 (`report-b`, pure): owner verdicts + trials → grade build → metrics. All drivers (chat-loop candidate, `claude -p` candidate) are injected via callbacks so the test suite never touches live MSTR or a live provider. Functional core, imperative shell: `records/b_trial.py`, `datasets/b_tasks.render_b_prompt`, `reports/b_scoring.py`, `reports/b_report.py` are pure; `runners/b_live.py`, `runners/b_candidate_chat.py`, `runners/b_candidate_claude.py`, `cli.py` are edges.

**Tech Stack:** Python ≥3.11, frozen dataclasses, `httpx`, `tomllib`, `pytest` (run via `uv run pytest`), `ruff` for lint/format. The candidate browse runtime reuses `runners/loop.run_single` + `tools/browse.BROWSE_TOOLS` + `runners/bash_edge.make_bash_executor`; the `claude -p` path reuses `runners/claude_cli_candidate` building blocks.

---

## Scope & guardrails (read before starting)

**OUT of scope for this build (owner-deferred per spec §9 — do NOT implement):**
- The live `MstrReadbackClient` readback / automated definition extraction / exact-grid compare. The existing fake-backed `runners/mstr_client.py`, `runners/b_isolation.py`, `datasets/b1_oracle.py`, `runners/b_run.py` stay in place, **unused by the live path** — do not delete or rewire them.
- Any paid sweep / live MSTR run / live provider call. This plan ships **code + tests + a runbook only**.
- OS-level `claude -p` confinement (seatbelt/restricted user). The spike ships a documented residual limitation + a store-relocation note in the runbook instead.

**Conventions every task MUST honor:**
- **STRICT TDD, red-green-refactor.** For every logic-bearing module the failing test step comes BEFORE the implementation step. Run the test, see it fail, then implement.
- **Pure modules** (`records/b_trial.py`, the `render_b_prompt` addition, `reports/b_scoring.py`, `reports/b_report.py`) contain NO I/O, NO mutation of arguments. Frozen dataclasses, return-new-values.
- **No live MSTR, no live provider anywhere in tests.** `candidate_run_fn` is injected (a fake returning a canned `Trajectory`); the `claude -p` path injects a fake `run_subprocess`; the CLI tests inject a `run_fn_factory`/`candidate_run_fn` like `_run_f_claude_baseline_command(args, *, run_fn_factory=None)` already does.
- **Mirror neighbouring idioms.** `runners/b_live.py` mirrors `runners/f_candidate.py`; the chat driver mirrors `runners/dset_run.py`'s executor wiring; the `claude -p` driver mirrors `runners/claude_cli_candidate.make_claude_run_fn`; the CLI commands mirror `_run_f_command` / `_run_f_claude_baseline_command`.
- **Tests run with `uv run pytest`.** Lint/format with `uv run ruff check .` and `uv run ruff format .` before each commit.
- Commit after each task with a `feat(b1-spike): …` / `refactor: …` / `test: …` message (the autodev/ship layer handles VERSION + CHANGELOG; do NOT bump them here).

**Grounding facts the tasks depend on (verified against the tree):**
- `runners/multi_run.py`: `run_task_k_valid` (lines 150-223) holds the D34 VOID math; `TrialAttempt` (125-130) and `ReplacementOutcome` (132-137) are frozen dataclasses; `_is_invalid` (139-147); `_run_one` (49-87).
- `runners/b_isolation.save_name_from_run_uid(run_uid)` (lines 18-25): slugs non-`[A-Za-z0-9._-]` to `-`, strips leading/trailing `-`, raises `ValueError` on empty.
- `runners/bash_edge.parse_argv(command)` (lines 45-76): rejects `(";", "|", "&", "`", "$(")`, rejects a `/` in `argv[0]`, returns argv or `None`. `ALLOWED_BINS = frozenset({"playwright-cli"})` (line 29).
- `runners/loop.run_single` (lines 124-139): keyword-only; key args `task, registry, config, http_client, run_index, temperature, max_tokens, apply_fn, executor, run_uid, safety_cap, max_rounds, health_probe_fn`.
- `tools/browse.BROWSE_TOOLS` (the single `bash` tool) + `apply_browse`.
- `records/grade.is_env_invalid_run(run)` reads `run.trajectory.parse_failure.error in (PROVIDER_ERROR, NO_CHOICES_ERROR)` and the grade `env_invalid` marker. The B path has **no grade**, so the runner's invalid check reads the trajectory directly (see Task 3).
- `records/trajectory.Trajectory`: frozen; `stop_reason` literal includes `"completed_natural" | "safety_cap" | "max_rounds" | "env_unhealthy" | "parse_failure"`; carries `rounds`, `wall_time_s`, `total_cost_usd`, `tool_call_counts`, `parse_failure`, `run_uid`, `max_rounds_bound`, `safety_cap_bound`. `PROVIDER_ERROR` / `NO_CHOICES_ERROR` constants live here.
- `runners/claude_cli_candidate`: `build_claude_argv`, `parse_claude_result`, `_sanitized_env`, `materialize_tree`, `read_back_tree`, `ClaudeResultParseError`, `_env_invalid_trajectory`, `ClaudeRunMeta`, `RunSubprocess`, `WorkdirFactory`.
- `experiments/evaluator_config.CandidateConfig` (lines 38-50): `url: str | None`, `username: str`, `password: str`. `load_evaluator_config` reads `[candidate]` `url`/`username`/`password`.
- `runners/loop.provider_auth_quota_status(trajectory) -> int | None` (401/403 only); `runners/config.PROVIDERS`, `condition_id`, `resolve_proxy`.
- `metrics/cost.TokenPrice` + `total_cost_usd`; `cli._load_prices(path)` returns `(snapshot_date, {condition_id: TokenPrice})`; `evaluator-only/pricing.json` shape: `{"snapshot_date", "prices": {condition_id: {input_per_mtok, output_per_mtok}}}`.
- `cli._slug(condition)`, `cli._append_runs(fh, runs)`, `records/serialize.run_result_to_dict`, `trajectory_to_dict`.

---

## File map

**Create:**
- `src/agent_eval_lab/records/b_trial.py` — the frozen grade-less `BTrial` record + `b_trial_to_dict`/`b_trial_from_dict`.
- `src/agent_eval_lab/runners/b_live.py` — B trial lifecycle + per-arm k-valid loop over an injected `candidate_run_fn`.
- `src/agent_eval_lab/runners/b_candidate_chat.py` — `make_b_chat_run_fn(...)` chat-loop candidate driver.
- `src/agent_eval_lab/runners/b_candidate_claude.py` — `make_b_claude_run_fn(...)` `claude -p` candidate driver.
- `src/agent_eval_lab/reports/b_scoring.py` — `emit_verdict_sheet(trials) -> (markdown, csv)`.
- `src/agent_eval_lab/reports/b_report.py` — `report_b(trials, verdicts) -> BReport`.
- `tests/records/test_b_trial.py`
- `tests/runners/test_b_live.py`
- `tests/runners/test_b_candidate_chat.py`
- `tests/runners/test_b_candidate_claude.py`
- `tests/reports/test_b_scoring.py`
- `tests/reports/test_b_report.py`
- `tests/cli/test_run_b.py`
- `tests/cli/test_report_b.py`
- `tests/runners/test_b_integrity_guard.py`

**Modify:**
- `src/agent_eval_lab/runners/multi_run.py` — extract `run_trials_k_valid` (behavior-preserving); refactor `run_task_k_valid` to call it.
- `src/agent_eval_lab/runners/bash_edge.py` — add `file:`-scheme reject in `parse_argv`.
- `src/agent_eval_lab/datasets/b_tasks.py` — add `render_b_prompt(...)`.
- `src/agent_eval_lab/experiments/evaluator_config.py` — extend `CandidateConfig` with `folder` (read `[candidate] folder`); confirm `url`/`password` reads.
- `src/agent_eval_lab/cli.py` — add `run-b` + `report-b` commands + their parsers + `main` dispatch.
- `tests/runners/test_multi_run.py` — add the `run_trials_k_valid` parity test.
- `tests/runners/test_bash_edge.py` — add the `file://` reject test.
- `tests/datasets/test_b_tasks.py` — add `render_b_prompt` tests.
- `tests/experiments/` config-loader test (locate the existing evaluator_config test; add a `folder` assertion).
- `docs/2026-06-13-agentic-v1-domains-runs/` run docs — append the B-1 live-run runbook.

---

## Phase 1 — `run_trials_k_valid` extraction (spec §11.1)

Behavior-preserving refactor: pull the D34 VOID/replacement arithmetic out of `run_task_k_valid` into a generic helper so `b_live` can reuse it. **Precondition for `b_live`.** Prove parity FIRST.

### Task 1: Parity test for the existing `run_task_k_valid`, then extract `run_trials_k_valid`

**Files:**
- Modify: `src/agent_eval_lab/runners/multi_run.py` (extract from lines 150-223)
- Test: `tests/runners/test_multi_run.py` (append)

- [ ] **Step 1: Write the failing parity test for the new generic helper**

Append to `tests/runners/test_multi_run.py`. This test drives `run_trials_k_valid` over a list of pre-canned `RunResult`s via an injected `trial_fn`, asserting the same VOID math the existing `run_task_k_valid` tests cover (replacement until k valid; best-case-under-threshold no-VOID; VOID when invalid-rate exceeded).

```python
def test_run_trials_k_valid_extracts_the_d34_arithmetic() -> None:
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.multi_run import run_trials_k_valid

    def _run(idx: int) -> RunResult:
        return RunResult(
            task_id="t",
            condition_id="c",
            run_index=idx,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
                run_index=idx,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
        )

    made: list[int] = []

    def trial_fn(attempt_index: int) -> RunResult:
        made.append(attempt_index)
        return _run(attempt_index)

    # attempt 0 invalid, the rest valid -> one replacement, no VOID.
    invalid_attempts = {0}

    def is_invalid(run: RunResult) -> bool:
        return run.run_index in invalid_attempts

    outcome = run_trials_k_valid(
        trial_fn=trial_fn,
        k_valid=2,
        max_invalid_rate=0.6,
        is_invalid_fn=is_invalid,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 2
    assert [a.attempt_index for a in outcome.attempts] == [0, 1, 2]
    assert made == [0, 1, 2]


def test_run_trials_k_valid_voids_when_rate_exceeded() -> None:
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage
    from agent_eval_lab.runners.multi_run import run_trials_k_valid

    def trial_fn(attempt_index: int) -> RunResult:
        return RunResult(
            task_id="t",
            condition_id="c",
            run_index=attempt_index,
            trajectory=Trajectory(
                turns=(),
                usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
                run_index=attempt_index,
                stop_reason="completed_natural",
            ),
            grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
        )

    outcome = run_trials_k_valid(
        trial_fn=trial_fn,
        k_valid=2,
        max_invalid_rate=0.4,
        is_invalid_fn=lambda run: True,  # every trial invalid
    )
    assert outcome.void is True
    assert len(outcome.valid_runs) < 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/runners/test_multi_run.py::test_run_trials_k_valid_extracts_the_d34_arithmetic -q`
Expected: FAIL — `ImportError: cannot import name 'run_trials_k_valid'`.

- [ ] **Step 3: Extract the helper in `multi_run.py`**

Add `run_trials_k_valid` ABOVE `run_task_k_valid`. Copy the exact VOID arithmetic (preserving the comment block at lines 204-211). It takes a `trial_fn(attempt_index) -> RunResult` and an `is_invalid_fn(run) -> bool` and owns ONLY the loop/replacement/VOID logic — no provider, no `_run_one`, no `condition_id`.

```python
def run_trials_k_valid(
    *,
    trial_fn: "Callable[[int], RunResult]",
    k_valid: int,
    max_invalid_rate: float,
    is_invalid_fn: "Callable[[RunResult], bool]",
) -> ReplacementOutcome:
    """D34 replacement-trial arithmetic, generic over the trial producer.

    Run `trial_fn(attempt_index)` until exactly `k_valid` valid trials are banked;
    a trial is invalid iff `is_invalid_fn(run)`. On invalid, a replacement runs
    immediately. VOID when even the best achievable final invalid-rate would exceed
    `max_invalid_rate` (the same predicate `run_task_k_valid` used) — never scored
    over fewer than k_valid valid runs. The subtle VOID math lives ONLY here."""
    attempts: list[TrialAttempt] = []
    valid_runs: list[RunResult] = []
    invalid_count = 0
    attempt_index = 0
    while len(valid_runs) < k_valid:
        run = trial_fn(attempt_index)
        invalid = is_invalid_fn(run)
        attempts.append(
            TrialAttempt(attempt_index=attempt_index, valid=not invalid, run=run)
        )
        if invalid:
            invalid_count += 1
        else:
            valid_runs.append(run)
        attempt_index += 1
        # VOID when even the BEST achievable final invalid-rate would exceed the
        # threshold (D28/D34). Best case = every remaining trial is valid, so the
        # final trial count is (invalid_count + k_valid) and the minimum reachable
        # invalid-rate is invalid_count / (invalid_count + k_valid). If that already
        # exceeds the cap, completing within k_valid valid trials is impossible ->
        # VOID. Using (invalid + k_valid) — not (invalid + remaining_needed) — keeps
        # already-banked valid runs in the denominator, so a condition is never
        # voided while a within-threshold completion is still reachable.
        if (
            len(valid_runs) < k_valid
            and (invalid_count / (invalid_count + k_valid)) > max_invalid_rate
        ):
            return ReplacementOutcome(
                valid_runs=tuple(valid_runs),
                attempts=tuple(attempts),
                void=True,
            )
    return ReplacementOutcome(
        valid_runs=tuple(valid_runs), attempts=tuple(attempts), void=False
    )
```

- [ ] **Step 4: Refactor `run_task_k_valid` to delegate (behavior-preserving)**

Replace the loop body of `run_task_k_valid` (lines 175-223) with a `trial_fn` closure + a delegating call. Keep the `_is_invalid(run, validity_fn)` semantics by wrapping it. The signature and all callers stay identical.

```python
def run_task_k_valid(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    validity_fn: "Callable[[RunResult], bool] | None" = None,
    health_probe_fn: "Callable[[], EnvHealth] | None" = None,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
    safety_cap: int = 200,
    max_rounds: int | None = None,
) -> ReplacementOutcome:
    """D34 replacement-trial loop: run until exactly k_valid valid trials.

    Thin task-specific wrapper over run_trials_k_valid: the trial producer is a
    `_run_one` per attempt_index, and invalidity is `_is_invalid` (env-unhealthy
    OR validity_fn). The VOID arithmetic lives in run_trials_k_valid."""
    condition = condition_id(config)

    def trial_fn(attempt_index: int) -> RunResult:
        return _run_one(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=attempt_index,
            condition=condition,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=apply_fn,
            executor=executor,
            health_probe_fn=health_probe_fn,
            safety_cap=safety_cap,
            max_rounds=max_rounds,
        )

    return run_trials_k_valid(
        trial_fn=trial_fn,
        k_valid=k_valid,
        max_invalid_rate=max_invalid_rate,
        is_invalid_fn=lambda run: _is_invalid(run, validity_fn),
    )
```

Ensure `RunResult` is imported at module top (it is — line 10 imports `GradeResult, RunResult`).

- [ ] **Step 5: Run the new helper tests + the FULL existing `multi_run` suite (parity proof)**

Run: `uv run pytest tests/runners/test_multi_run.py -q`
Expected: PASS — both new tests pass AND every pre-existing `run_task_k_valid` test (replace-until-k, no-void-best-case, void-when-exceeded, env-unhealthy-counts-as-invalid, forwards-max-rounds) still passes. This is the behavior-preserving proof.

- [ ] **Step 6: Lint + commit**

```bash
uv run ruff format src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
uv run ruff check src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git add src/agent_eval_lab/runners/multi_run.py tests/runners/test_multi_run.py
git commit -m "refactor: extract run_trials_k_valid from run_task_k_valid (behavior-preserving)"
```

**Verification point:** `uv run pytest tests/runners/test_multi_run.py -q` is all green. The D34 VOID math now lives in exactly one place.

---

## Phase 2 — `BTrial` record (spec §11.2 / §5 / ADR-0021)

The grade-less, frozen, serializable on-disk unit of `trials-b-*.jsonl`.

### Task 2: `BTrial` record + serialization

**Files:**
- Create: `src/agent_eval_lab/records/b_trial.py`
- Test: `tests/records/test_b_trial.py`

- [ ] **Step 1: Write the failing test**

```python
from agent_eval_lab.records.b_trial import (
    BTrial,
    b_trial_from_dict,
    b_trial_to_dict,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _traj() -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=1.0),
        run_index=2,
        stop_reason="completed_natural",
        rounds=7,
        wall_time_s=12.5,
        run_uid="dashscope-qwen3.7-max__b-b1-noskill__0002",
    )


def test_btrial_is_frozen_and_grade_less() -> None:
    trial = BTrial(
        run_uid="dashscope-qwen3.7-max__b-b1-noskill__0002",
        condition_id="dashscope:qwen3.7-max",
        task_id="b-b1-noskill",
        save_name="dashscope-qwen3.7-max__b-b1-noskill__0002",
        folder="/Candidate/bxu",
        trajectory=_traj(),
        invalid=False,
        invalid_reason=None,
    )
    assert not hasattr(trial, "grade")
    import dataclasses

    try:
        trial.invalid = True  # type: ignore[misc]
        raise AssertionError("BTrial must be frozen")
    except dataclasses.FrozenInstanceError:
        pass


def test_btrial_round_trips_through_dict() -> None:
    trial = BTrial(
        run_uid="dashscope-qwen3.7-max__b-b1-skill__0001",
        condition_id="dashscope:qwen3.7-max",
        task_id="b-b1-skill",
        save_name="dashscope-qwen3.7-max__b-b1-skill__0001",
        folder="/Candidate/bxu",
        trajectory=_traj(),
        invalid=True,
        invalid_reason="provider_error",
    )
    restored = b_trial_from_dict(b_trial_to_dict(trial))
    assert restored == trial
    # invalid_reason and the trajectory survive the round-trip.
    assert restored.invalid_reason == "provider_error"
    assert restored.trajectory.rounds == 7
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/records/test_b_trial.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.records.b_trial`.

- [ ] **Step 3: Implement `records/b_trial.py`**

Reuse `trajectory_to_dict` / `trajectory_from_dict` from `records/serialize.py` so the Trajectory round-trip is single-sourced (mirrors how `run_result_to_dict` delegates).

```python
"""The grade-less B-set trial record (ADR-0021).

`BTrial` is the on-disk unit of `trials-b-*.jsonl`: everything `run-b` records for
one trial EXCEPT the grade. The grade is the later **owner verdict** (CONTEXT.md:
*owner verdict*), joined to the trial at report time by `report_b` — never a
`GradeResult` fabricated at run time. Frozen + serializable; the Trajectory
round-trip delegates to records/serialize so it stays single-sourced.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.serialize import trajectory_from_dict, trajectory_to_dict
from agent_eval_lab.records.trajectory import Trajectory

# The auto-tag the runner stamps when a trial did not get a fair trial. None for a
# valid (gradeable) trial. "provider_error" / "no_choices" are provider-side
# (is_env_invalid analogue); "env_unhealthy" is health-probe-side.
InvalidReason = Literal["provider_error", "no_choices", "env_unhealthy"]


@dataclass(frozen=True, kw_only=True)
class BTrial:
    run_uid: str
    condition_id: str
    task_id: str  # the ARM: b-b1-noskill / b-b1-skill (arm rides task_id, CONTEXT.md)
    save_name: str
    folder: str
    trajectory: Trajectory
    invalid: bool
    invalid_reason: InvalidReason | None = None


def b_trial_to_dict(trial: BTrial) -> dict[str, Any]:
    return {
        "run_uid": trial.run_uid,
        "condition_id": trial.condition_id,
        "task_id": trial.task_id,
        "save_name": trial.save_name,
        "folder": trial.folder,
        "trajectory": trajectory_to_dict(trial.trajectory),
        "invalid": trial.invalid,
        "invalid_reason": trial.invalid_reason,
    }


def b_trial_from_dict(data: Mapping[str, Any]) -> BTrial:
    return BTrial(
        run_uid=data["run_uid"],
        condition_id=data["condition_id"],
        task_id=data["task_id"],
        save_name=data["save_name"],
        folder=data["folder"],
        trajectory=trajectory_from_dict(data["trajectory"]),
        invalid=data["invalid"],
        invalid_reason=data.get("invalid_reason"),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/records/test_b_trial.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/agent_eval_lab/records/b_trial.py tests/records/test_b_trial.py
uv run ruff check src/agent_eval_lab/records/b_trial.py tests/records/test_b_trial.py
git add src/agent_eval_lab/records/b_trial.py tests/records/test_b_trial.py
git commit -m "feat(b1-spike): add grade-less BTrial record (ADR-0021)"
```

**Verification point:** `uv run pytest tests/records/test_b_trial.py -q` green; `BTrial` has no `grade` field and round-trips.

---

## Phase 3 — `b_live.py` trial lifecycle + per-arm k-valid loop (spec §11.3 / §6)

### Task 3: `b_live` invalid-tagging + per-arm k-valid loop over an injected `candidate_run_fn`

**Files:**
- Create: `src/agent_eval_lab/runners/b_live.py`
- Test: `tests/runners/test_b_live.py`

`candidate_run_fn` has signature `(task: Task, run_index: int, save_name: str) -> Trajectory` (spec §5). Per trial: derive the task-scoped `run_uid` (§6.1) → `save_name` → call `candidate_run_fn` → auto-tag invalid → wrap as a grade-less `BTrial`. The k-valid loop reuses `run_trials_k_valid` (Task 1). Invalid detection reads the Trajectory directly (the B path has no grade), matching `records/grade.is_env_invalid_run`'s provider-side branch + the `env_unhealthy` stop.

- [ ] **Step 1: Write the failing tests**

```python
from agent_eval_lab.records.trajectory import (
    PROVIDER_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.runners.b_live import (
    b_trial_run_uid,
    classify_invalid,
    run_b_arm,
)
from agent_eval_lab.tasks.schema import Task, TaskInput


def _task(task_id: str) -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id=task_id,
        capability="browser_mstr",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="build it"),),
            available_tools=("bash",),
        ),
        # B grades by owner verdict, never an automated spec at run time; the live
        # path never reads task.verification, so a minimal AllOf(specs=()) suffices
        # (Task.verification is non-optional: schema.py Task.verification: VerificationSpec).
        verification=AllOf(specs=()),
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def _ok(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=run_index,
        stop_reason="completed_natural",
        rounds=3,
    )


def _provider_fail(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw="403", error=PROVIDER_ERROR),
    )


def _max_rounds(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=run_index,
        stop_reason="max_rounds",
        rounds=50,
        max_rounds_bound=True,
    )


def test_run_uid_is_task_scoped() -> None:
    uid = b_trial_run_uid(
        condition_id="dashscope:qwen3.7-max", task_id="b-b1-noskill", run_index=2
    )
    assert uid == "dashscope:qwen3.7-max__b-b1-noskill__0002"


def test_provider_failure_is_invalid_max_rounds_is_not() -> None:
    assert classify_invalid(_provider_fail(0)) == "provider_error"
    # A max_rounds cap is a CENSORED task-failure, never invalid (spec §6.3).
    assert classify_invalid(_max_rounds(0)) is None
    assert classify_invalid(_ok(0)) is None


def test_run_b_arm_wraps_grade_less_btrials_with_save_names() -> None:
    seen: list[tuple[str, int, str]] = []

    def candidate_run_fn(task, run_index, save_name):
        seen.append((task.id, run_index, save_name))
        return _ok(run_index)

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.4,
    )
    assert outcome.void is False
    assert len(outcome.trials) == 3
    # Each trial carries its task-scoped save-name and NO grade.
    assert outcome.trials[0].save_name == (
        "dashscope-qwen3.7-max__b-b1-noskill__0000"
    )
    assert all(not hasattr(t, "grade") for t in outcome.trials)
    assert all(t.invalid is False for t in outcome.trials)
    # The candidate driver was handed the rendered save-name per trial.
    assert seen[0][2] == "dashscope-qwen3.7-max__b-b1-noskill__0000"


def test_run_b_arm_replaces_provider_invalid_until_k_valid() -> None:
    scripted = [_provider_fail(0), _ok(1), _ok(2), _ok(3)]
    calls = [0]

    def candidate_run_fn(task, run_index, save_name):
        traj = scripted[calls[0]]
        calls[0] += 1
        return traj

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.5,
    )
    assert outcome.void is False
    assert len(outcome.trials) == 3  # only VALID trials are banked
    # The invalid attempt is recorded in attempts with its reason.
    invalid = [t for t in outcome.all_trials if t.invalid]
    assert len(invalid) == 1
    assert invalid[0].invalid_reason == "provider_error"


def test_run_b_arm_voids_when_invalid_rate_exceeded() -> None:
    def candidate_run_fn(task, run_index, save_name):
        return _provider_fail(run_index)

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.4,
    )
    assert outcome.void is True
    assert len(outcome.trials) < 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/runners/test_b_live.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.runners.b_live`.

- [ ] **Step 3: Implement `runners/b_live.py`**

```python
"""EDGE: B-set trial lifecycle + per-arm k-valid loop (spec §6, §11.3).

Per trial: derive the TASK-SCOPED run_uid (arm rides task_id) -> save_name (reuse
b_isolation.save_name_from_run_uid) -> call the injected candidate_run_fn(task,
run_index, save_name) -> auto-tag env/provider INVALID -> wrap as a grade-less
BTrial (ADR-0021; the grade is the later owner verdict). Runs to k_valid valid
trials with env-invalid replacement via the shared run_trials_k_valid helper
(spec §11.1). A max_rounds/safety_cap stop is CENSORED (a task failure for the
verdict), NOT invalid (spec §6.3 / CONTEXT.md: censoring).

candidate_run_fn is injected so the test suite needs no live MSTR or live provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from agent_eval_lab.records.b_trial import BTrial, InvalidReason
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    PROVIDER_ERROR,
    Trajectory,
)
from agent_eval_lab.runners.b_isolation import save_name_from_run_uid
from agent_eval_lab.runners.multi_run import run_trials_k_valid
from agent_eval_lab.tasks.schema import Task

# Same callback shape across the chat and claude -p candidate drivers (spec §5).
CandidateRunFn = Callable[[Task, int, str], Trajectory]


def b_trial_run_uid(*, condition_id: str, task_id: str, run_index: int) -> str:
    """The TASK-SCOPED run_uid (§6.1 / CONTEXT.md: run_uid). The arm rides task_id;
    a non-task-scoped uid collides across arms."""
    return f"{condition_id}__{task_id}__{run_index:04d}"


def classify_invalid(trajectory: Trajectory) -> InvalidReason | None:
    """Auto-tag a trial INVALID iff the model never got a fair trial — a provider
    HTTP rejection / empty-choices (the is_env_invalid_run provider-side branch) or
    an env-unhealthy health probe. A max_rounds / safety_cap cap is CENSORED, not
    invalid (spec §6.3). Returns the reason, or None for a valid (gradeable) trial."""
    if trajectory.stop_reason == "env_unhealthy":
        return "env_unhealthy"
    pf = trajectory.parse_failure
    if pf is not None and pf.error == PROVIDER_ERROR:
        return "provider_error"
    if pf is not None and pf.error == NO_CHOICES_ERROR:
        return "no_choices"
    return None


@dataclass(frozen=True, kw_only=True)
class BArmOutcome:
    trials: tuple[BTrial, ...]  # the k_valid VALID trials (banked)
    all_trials: tuple[BTrial, ...]  # every attempt incl. invalid replacements
    void: bool


def _btrial_from_trajectory(
    *, trajectory: Trajectory, condition_id: str, task_id: str, folder: str
) -> BTrial:
    run_uid = b_trial_run_uid(
        condition_id=condition_id, task_id=task_id, run_index=trajectory.run_index
    )
    reason = classify_invalid(trajectory)
    return BTrial(
        run_uid=run_uid,
        condition_id=condition_id,
        task_id=task_id,
        save_name=save_name_from_run_uid(run_uid),
        folder=folder,
        trajectory=trajectory,
        invalid=reason is not None,
        invalid_reason=reason,
    )


def run_b_arm(
    *,
    task: Task,
    condition_id: str,
    folder: str,
    candidate_run_fn: CandidateRunFn,
    k_valid: int,
    max_invalid_rate: float,
) -> BArmOutcome:
    """Run ONE arm (task) to k_valid valid trials with D34 env-invalid replacement.

    The trial producer derives the save-name from the task-scoped run_uid and hands
    it to candidate_run_fn; run_trials_k_valid owns the VOID arithmetic. Because that
    helper is typed over RunResult, each trial is wrapped in a thin grade-less
    RunResult-shaped adapter for the loop only — the BTrial is the real record we
    keep (the adapter's GradeResult is a placeholder the loop never inspects beyond
    is_invalid_fn, which reads the trajectory, never the grade)."""
    captured: dict[int, BTrial] = {}

    def trial_fn(attempt_index: int) -> RunResult:
        run_uid = b_trial_run_uid(
            condition_id=condition_id, task_id=task.id, run_index=attempt_index
        )
        save_name = save_name_from_run_uid(run_uid)
        trajectory = candidate_run_fn(task, attempt_index, save_name)
        captured[attempt_index] = _btrial_from_trajectory(
            trajectory=trajectory,
            condition_id=condition_id,
            task_id=task.id,
            folder=folder,
        )
        # Adapter: run_trials_k_valid is typed over RunResult. The grade is a
        # placeholder; is_invalid_fn below reads the trajectory, never this grade.
        return RunResult(
            task_id=task.id,
            condition_id=condition_id,
            run_index=attempt_index,
            trajectory=trajectory,
            grade=GradeResult(
                grader_id="b-live-placeholder", passed=False, score=0.0, evidence={}
            ),
        )

    outcome = run_trials_k_valid(
        trial_fn=trial_fn,
        k_valid=k_valid,
        max_invalid_rate=max_invalid_rate,
        is_invalid_fn=lambda run: classify_invalid(run.trajectory) is not None,
    )
    trials = tuple(captured[r.run_index] for r in outcome.valid_runs)
    all_trials = tuple(captured[a.attempt_index] for a in outcome.attempts)
    return BArmOutcome(trials=trials, all_trials=all_trials, void=outcome.void)
```

NOTE (grounded): `Task.verification` is **non-optional** (`schema.py:213` — `verification: VerificationSpec`). The B live path never reads it, so `run_b_arm` works with any schema-valid value. Test helpers and `_make_live_b_task` (Task 9) construct tasks with `AllOf(specs=())` (the minimal valid `VerificationSpec`, `schema.py:83-85`, a kw-only frozen dataclass). Do NOT pass `verification=None` — it would fail construction.

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/runners/test_b_live.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/agent_eval_lab/runners/b_live.py tests/runners/test_b_live.py
uv run ruff check src/agent_eval_lab/runners/b_live.py tests/runners/test_b_live.py
git add src/agent_eval_lab/runners/b_live.py tests/runners/test_b_live.py
git commit -m "feat(b1-spike): add b_live trial lifecycle + per-arm k-valid loop"
```

**Verification point:** `uv run pytest tests/runners/test_b_live.py -q` green; task-scoped run_uid + save-name derivation, provider-invalid replacement, max_rounds-is-censored-not-invalid, and VOID all proven against fakes.

---

## Phase 4 — `file://` guard in `bash_edge.parse_argv` (spec §11.4 / §7)

### Task 4: Reject a `file:`-scheme `playwright-cli` argument

**Files:**
- Modify: `src/agent_eval_lab/runners/bash_edge.py:45-76` (`parse_argv`)
- Test: `tests/runners/test_bash_edge.py` (append)

The candidate must not read local files via browser `file://` navigation (`playwright-cli open file:///…/evaluator.toml`). Reject any argv token whose lowercased form starts with `file:` (covers `file://`, `file:///`, `FILE://`).

- [ ] **Step 1: Write the failing tests**

```python
def test_parse_argv_rejects_file_scheme_navigation() -> None:
    from agent_eval_lab.runners.bash_edge import parse_argv

    assert parse_argv("playwright-cli -s=x open file:///etc/passwd") is None
    assert parse_argv("playwright-cli open file://localhost/evaluator.toml") is None
    # Case-insensitive: FILE:// is also refused.
    assert parse_argv("playwright-cli open FILE:///x") is None


def test_parse_argv_still_allows_http_and_arrow_functions() -> None:
    from agent_eval_lab.runners.bash_edge import parse_argv

    assert parse_argv("playwright-cli -s=x open https://lab/app") == [
        "playwright-cli",
        "-s=x",
        "open",
        "https://lab/app",
    ]
    # The existing arrow-function eval must keep parsing (no false positive).
    assert parse_argv(
        'playwright-cli -s=x eval "() => document.body.innerText"'
    ) == ["playwright-cli", "-s=x", "eval", "() => document.body.innerText"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/runners/test_bash_edge.py::test_parse_argv_rejects_file_scheme_navigation -q`
Expected: FAIL — the `file://` argv is currently returned, not `None`.

- [ ] **Step 3: Add the guard in `parse_argv`**

After the `shlex.split` succeeds and `argv` is non-empty, before the `argv[0]` slash check, add the file-scheme reject over every token:

```python
    if not argv:
        return None
    # Browser file:// navigation is a read-the-store vector (§7): a
    # `playwright-cli open file:///…/evaluator.toml` + eval would exfiltrate the
    # integrity store. Refuse any file:-scheme argument (case-insensitive). HTTP(S)
    # navigation is unaffected.
    if any(tok.lower().startswith("file:") for tok in argv):
        return None
    # The allowlist is name-based ...
    if "/" in argv[0]:
        return None
    return argv
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/runners/test_bash_edge.py -q`
Expected: PASS — the new tests pass AND every existing `bash_edge` test still passes (no regression on the arrow-function / http cases).

- [ ] **Step 5: Lint + commit**

```bash
uv run ruff format src/agent_eval_lab/runners/bash_edge.py tests/runners/test_bash_edge.py
uv run ruff check src/agent_eval_lab/runners/bash_edge.py tests/runners/test_bash_edge.py
git add src/agent_eval_lab/runners/bash_edge.py tests/runners/test_bash_edge.py
git commit -m "feat(b1-spike): reject file:-scheme playwright-cli args (chat-loop file:// guard)"
```

**Verification point:** `uv run pytest tests/runners/test_bash_edge.py -q` green; `file://` blocked, `https://` + arrow-functions unaffected.

---

## Phase 5 — Chat candidate driver + `render_b_prompt` (spec §11.5 / §5 / §6.2)

### Task 5a: `render_b_prompt` (pure prompt injection)

**Files:**
- Modify: `src/agent_eval_lab/datasets/b_tasks.py`
- Test: `tests/datasets/test_b_tasks.py` (append)

Inject the per-trial save-name + candidate login (app URL / user) + target folder into the static B-1 user prompt. The function NEVER injects the password into the prompt text (the candidate logs in via its account; the prompt names the URL/user/folder/save-name only — the password is handed to the live session out-of-band, never into the model context). Spec §8: "render_b_prompt substitution + that it never leaks evaluator creds".

- [ ] **Step 1: Write the failing tests**

```python
def test_render_b_prompt_injects_save_name_login_and_folder() -> None:
    from agent_eval_lab.datasets.b_tasks import render_b_prompt

    rendered = render_b_prompt(
        "Build the report and save it.",
        save_name="dashscope-qwen3.7-max__b-b1-noskill__0002",
        login=("https://lab/MicroStrategyLibrary/app", "bxu"),
        folder="/Candidate/bxu",
    )
    assert "dashscope-qwen3.7-max__b-b1-noskill__0002" in rendered
    assert "https://lab/MicroStrategyLibrary/app" in rendered
    assert "bxu" in rendered
    assert "/Candidate/bxu" in rendered
    # The static instruction is preserved.
    assert "Build the report and save it." in rendered


def test_render_b_prompt_never_leaks_the_password() -> None:
    from agent_eval_lab.datasets.b_tasks import render_b_prompt

    rendered = render_b_prompt(
        "Build it.",
        save_name="m__b-b1-skill__0000",
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
    )
    # render_b_prompt has no password parameter at all — the credential never
    # enters the model context. Guard against a future regression that adds one.
    assert "password" not in rendered.lower()
    import inspect

    sig = inspect.signature(render_b_prompt)
    assert "password" not in sig.parameters
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/datasets/test_b_tasks.py::test_render_b_prompt_injects_save_name_login_and_folder -q`
Expected: FAIL — `ImportError: cannot import name 'render_b_prompt'`.

- [ ] **Step 3: Implement `render_b_prompt` in `datasets/b_tasks.py`**

Add below `build_b_tasks` (keep `build_b_tasks` unchanged). The login is a `(app_url, username)` tuple — no password parameter exists.

```python
def render_b_prompt(
    base_user: str,
    *,
    save_name: str,
    login: tuple[str, str],
    folder: str,
) -> str:
    """Inject the per-trial save-name + candidate login (app URL / username) +
    target folder into the static B-1 user prompt (spec §6.2). PURE.

    `login` is (app_url, username); there is DELIBERATELY no password parameter —
    the credential is handed to the live browser session out-of-band and NEVER
    enters the model context (§7 integrity boundary / TRAP 2)."""
    app_url, username = login
    return (
        f"{base_user}\n\n"
        f"Log in to the MicroStrategy Library app at {app_url} as user "
        f"{username!r} (the session is already authenticated for you; do not ask "
        f"for or print credentials). Save the report to the folder {folder!r} "
        f"under EXACTLY the unique name {save_name!r}."
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/datasets/test_b_tasks.py -q`
Expected: PASS — new tests pass AND the existing `build_b_tasks` tests still pass.

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/agent_eval_lab/datasets/b_tasks.py tests/datasets/test_b_tasks.py
uv run ruff check src/agent_eval_lab/datasets/b_tasks.py tests/datasets/test_b_tasks.py
git add src/agent_eval_lab/datasets/b_tasks.py tests/datasets/test_b_tasks.py
git commit -m "feat(b1-spike): add pure render_b_prompt (save-name + login + folder, no password)"
```

### Task 5b: `b_candidate_chat.make_b_chat_run_fn` (chat-loop candidate driver)

**Files:**
- Create: `src/agent_eval_lab/runners/b_candidate_chat.py`
- Test: `tests/runners/test_b_candidate_chat.py`

The chat-loop candidate driver for qwen-max / deepseek / MiniMax: per trial, build an isolated playwright-cli session + workdir via `make_bash_executor` (allowlist `{"playwright-cli"}`), rebuild the task's user message with `render_b_prompt(save_name)`, and run the browse loop via `run_single` + `BROWSE_TOOLS`, `max_rounds=50`. Same `(task, run_index, save_name) -> Trajectory` callback shape as the claude driver.

- [ ] **Step 1: Write the failing test (injected executor-factory + a fake `run_single`)**

`make_bash_executor` does real fs work; inject an `executor_factory` so the test needs no playwright-cli and no fs. Inject `run_single` via the factory's parameter so the test asserts the wiring (registry == BROWSE_TOOLS, max_rounds == 50, run_uid passed, the rendered save-name in the task's user message) without a live provider.

```python
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.b_candidate_chat import make_b_chat_run_fn
from agent_eval_lab.tasks.schema import Task, TaskInput


def _task() -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id="b-b1-noskill",
        capability="browser_mstr",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content="sys"),
                MessageTurn(role="user", content="Build the B-1 report."),
            ),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),  # live path never grades; minimal valid spec
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def test_chat_run_fn_wires_browse_loop_with_rendered_save_name(tmp_path) -> None:
    captured = {}

    def fake_run_single(**kwargs):
        captured.update(kwargs)
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
            rounds=4,
        )

    closes = []

    def fake_executor_factory(*, session_id, workdir):
        def executor(req):  # never called by the fake run_single
            raise AssertionError("executor should not run under a fake run_single")

        closes.append(session_id)
        return executor, lambda: None

    run_fn = make_b_chat_run_fn(
        config=object(),  # opaque; the fake run_single ignores it
        http_client=object(),
        temperature=0.0,
        max_tokens=4096,
        condition_id="dashscope:qwen3.7-max",
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
        workdir_root=tmp_path,
        executor_factory=fake_executor_factory,
        run_single_fn=fake_run_single,
    )
    traj = run_fn(_task(), 2, "dashscope-qwen3.7-max__b-b1-noskill__0002")

    assert traj.rounds == 4
    # browse-world registry + the 50-round cap + the task-scoped run_uid.
    from agent_eval_lab.tools.browse import BROWSE_TOOLS

    assert captured["registry"] is BROWSE_TOOLS
    assert captured["max_rounds"] == 50
    assert captured["run_uid"] == "dashscope:qwen3.7-max__b-b1-noskill__0002"
    # The rendered user message carries the save-name + folder + app url.
    rebuilt = captured["task"]
    user = next(m for m in rebuilt.input.messages if m.role == "user")
    assert "dashscope-qwen3.7-max__b-b1-noskill__0002" in user.content
    assert "/Candidate/bxu" in user.content
    assert "https://lab/app" in user.content
    # The system message is preserved (skill arm injection lives upstream).
    assert any(m.role == "system" and m.content == "sys" for m in rebuilt.input.messages)


def test_chat_run_fn_closes_the_executor(tmp_path) -> None:
    closed = []

    def fake_run_single(**kwargs):
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
        )

    def fake_executor_factory(*, session_id, workdir):
        return (lambda req: None), (lambda: closed.append(session_id))

    run_fn = make_b_chat_run_fn(
        config=object(),
        http_client=object(),
        temperature=0.0,
        max_tokens=4096,
        condition_id="c",
        login=("u", "bxu"),
        folder="/f",
        workdir_root=tmp_path,
        executor_factory=fake_executor_factory,
        run_single_fn=fake_run_single,
    )
    run_fn(_task(), 0, "save0")
    assert closed  # the per-trial executor was closed even on the happy path
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/runners/test_b_candidate_chat.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.runners.b_candidate_chat`.

- [ ] **Step 3: Implement `runners/b_candidate_chat.py`**

```python
"""EDGE: the chat-loop B-set candidate driver (spec §5 / §11.5).

For qwen-max / deepseek / MiniMax: each trial gets a FRESH playwright-cli session
+ isolated workdir (make_bash_executor, allowlist-confined to {"playwright-cli"}),
the static B-1 user prompt re-rendered with the per-trial save-name + candidate
login + folder (render_b_prompt), and the browse loop (run_single + BROWSE_TOOLS),
max_rounds=50. Same (task, run_index, save_name) -> Trajectory callback shape as
the claude -p driver, so b_live drives either identically.

make_bash_executor + run_single are injected (executor_factory / run_single_fn) so
the test suite needs no playwright-cli, no fs writes, and no live provider.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import httpx

from agent_eval_lab.datasets.b_tasks import render_b_prompt
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.bash_edge import make_bash_executor
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.schema import Task, TaskInput
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse

B_MAX_ROUNDS = 50  # spec §11.5 / decision 6 — keep 50, calibrate-first per runbook.


def _render_task(task: Task, *, save_name: str, login: tuple[str, str], folder: str) -> Task:
    """Re-render the user message with the per-trial save-name/login/folder; keep
    the system message (and any skill-arm injection) verbatim."""
    user = next((m for m in task.input.messages if m.role == "user"), None)
    base_user = user.content if user is not None else ""
    rendered_user = render_b_prompt(
        base_user, save_name=save_name, login=login, folder=folder
    )
    messages = tuple(
        MessageTurn(role="user", content=rendered_user) if m.role == "user" else m
        for m in task.input.messages
    )
    return replace(
        task, input=TaskInput(messages=messages, available_tools=task.input.available_tools)
    )


def make_b_chat_run_fn(
    *,
    config: ProviderConfig,
    http_client: httpx.Client,
    temperature: float,
    max_tokens: int,
    condition_id: str,
    login: tuple[str, str],
    folder: str,
    workdir_root: Path,
    max_rounds: int = B_MAX_ROUNDS,
    executor_factory: Callable[..., tuple[Callable, Callable[[], None]]] = make_bash_executor,
    run_single_fn: Callable[..., Trajectory] = run_single,
) -> Callable[[Task, int, str], Trajectory]:
    """Build the per-trial chat-loop candidate driver for one arm."""

    def run_fn(task: Task, run_index: int, save_name: str) -> Trajectory:
        rendered = _render_task(task, save_name=save_name, login=login, folder=folder)
        workdir = workdir_root / f"b-work-{save_name}"
        executor, close = executor_factory(session_id=save_name, workdir=workdir)
        try:
            return run_single_fn(
                task=rendered,
                registry=BROWSE_TOOLS,
                config=config,
                http_client=http_client,
                run_index=run_index,
                temperature=temperature,
                max_tokens=max_tokens,
                apply_fn=apply_browse,
                executor=executor,
                run_uid=f"{condition_id}__{task.id}__{run_index:04d}",
                max_rounds=max_rounds,
            )
        finally:
            close()

    return run_fn
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/runners/test_b_candidate_chat.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/agent_eval_lab/runners/b_candidate_chat.py tests/runners/test_b_candidate_chat.py
uv run ruff check src/agent_eval_lab/runners/b_candidate_chat.py tests/runners/test_b_candidate_chat.py
git add src/agent_eval_lab/runners/b_candidate_chat.py tests/runners/test_b_candidate_chat.py
git commit -m "feat(b1-spike): add chat-loop B candidate driver (browse loop, max_rounds=50)"
```

**Verification point:** `uv run pytest tests/runners/test_b_candidate_chat.py tests/datasets/test_b_tasks.py -q` green; the chat driver wires the browse loop with the rendered save-name and closes its executor; `render_b_prompt` never carries a password.

---

## Phase 6 — `claude -p` candidate driver (spec §11.6 / §5)

### Task 6: `b_candidate_claude.make_b_claude_run_fn`

**Files:**
- Create: `src/agent_eval_lab/runners/b_candidate_claude.py`
- Test: `tests/runners/test_b_candidate_claude.py`

The `claude -p` candidate driver: Bash + `playwright-cli` on PATH, reusing `claude_cli_candidate` building blocks (`build_claude_argv`-style argv, `parse_claude_result`, `_sanitized_env`, `_env_invalid_trajectory`). Same `(task, run_index, save_name) -> Trajectory` callback shape. Records `num_turns` (→ `rounds`) + `total_cost_usd`. `run_subprocess` + `workdir_factory` injected so the test needs no real `claude`. **NOT OS-confined — see §7 residual limitation (documented, not closed).**

- [ ] **Step 1: Write the failing tests (fake `run_subprocess` returns canned JSON, mirroring `test_claude_cli_candidate`)**

```python
import json
import subprocess

from agent_eval_lab.records.trajectory import PROVIDER_ERROR
from agent_eval_lab.runners.b_candidate_claude import make_b_claude_run_fn
from agent_eval_lab.tasks.schema import Task, TaskInput


class _FakeCompleted:
    def __init__(self, *, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _task() -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Build the B-1 report."),),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),  # live path never grades; minimal valid spec
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def _result_json(*, num_turns=6, total_cost_usd=0.0321, is_error=False):
    return json.dumps(
        {
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "num_turns": num_turns,
            "total_cost_usd": total_cost_usd,
            "is_error": is_error,
        }
    )


def test_claude_run_fn_success_records_turns_and_cost(tmp_path) -> None:
    captured = {}

    def fake_subprocess(argv, *, cwd, env, timeout):
        captured["argv"] = argv
        captured["env"] = env
        return _FakeCompleted(stdout=_result_json())

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
    )
    traj = run_fn(_task(), 1, "claude-cli-claude-sonnet-4-6__b-b1-skill__0001")
    assert traj.stop_reason == "completed_natural"
    assert traj.rounds == 6
    assert traj.total_cost_usd == 0.0321
    # The rendered prompt (last argv element) carries the save-name + folder.
    assert "claude-cli-claude-sonnet-4-6__b-b1-skill__0001" in captured["argv"][-1]
    assert "/Candidate/bxu" in captured["argv"][-1]
    # Bash is allowed for the live browser surface (not edit-only).
    assert "Bash" in " ".join(captured["argv"])


def test_claude_run_fn_nonzero_exit_is_env_invalid(tmp_path) -> None:
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="", stderr="boom", returncode=1)

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    traj = run_fn(_task(), 0, "save0")
    assert traj.stop_reason == "env_unhealthy"
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


def test_claude_run_fn_timeout_is_env_invalid(tmp_path) -> None:
    def fake_subprocess(argv, *, cwd, env, timeout):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    traj = run_fn(_task(), 0, "save0")
    assert traj.stop_reason == "env_unhealthy"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/runners/test_b_candidate_claude.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.runners.b_candidate_claude`.

- [ ] **Step 3: Implement `runners/b_candidate_claude.py`**

Reuse `parse_claude_result`, `_sanitized_env`, `_env_invalid_trajectory`, `ClaudeResultParseError` from `claude_cli_candidate`. Build a browser-surface argv (Bash allowed; the live MSTR surface needs native Bash + playwright-cli on PATH). The system prompt instructs driving playwright-cli to build the B-1 report. **This driver does NOT materialize a code tree** (unlike the F baseline) — there is no produced tree to read back; the candidate's effect is the saved MSTR object, graded later by the owner.

```python
"""EDGE: the `claude -p` B-set candidate driver (spec §5 / §11.6).

Reuses claude_cli_candidate building blocks (parse_claude_result, _sanitized_env,
_env_invalid_trajectory). Unlike the F baseline this driver materializes NO code
tree and reads NO tree back — the candidate's effect is the saved MSTR object,
graded later by the owner verdict (ADR-0021). It needs native Bash + playwright-cli
on PATH and the REAL HOME (OAuth in Keychain), so it is NOT OS-confined: the
spike's §7 residual limitation (mitigated by store relocation, not closed). Same
(task, run_index, save_name) -> Trajectory callback shape as the chat driver.

run_subprocess + workdir_factory are injected so the test suite needs no `claude`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from agent_eval_lab.datasets.b_tasks import render_b_prompt
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.claude_cli_candidate import (
    ClaudeResultParseError,
    RunSubprocess,
    WorkdirFactory,
    _env_invalid_trajectory,
    _sanitized_env,
    parse_claude_result,
)

_B_SYSTEM = (
    "You are automating the MicroStrategy Library web UI with playwright-cli (a "
    "headless browser) driven through Bash. Complete the owner-specified report "
    "build exactly; do not take shortcuts via APIs. When the saved report renders "
    "the prompted result, reply with a one-line summary and stop."
)

_ALLOWED_TOOLS = ("Bash",)
_DENIED_TOOLS = ("WebFetch", "WebSearch", "Task")


def _build_b_claude_argv(*, model: str, prompt: str, max_budget_usd: float) -> list[str]:
    """The `claude -p` argv for one B trial: --safe-mode (vanilla), Bash allowed for
    the live browser surface. No --max-turns in the CLI; the subprocess timeout +
    --max-budget-usd bound the run (cf. claude_cli_candidate.build_claude_argv)."""
    return [
        "claude",
        "-p",
        "--model",
        model,
        "--output-format",
        "json",
        "--safe-mode",
        "--disable-slash-commands",
        "--append-system-prompt",
        _B_SYSTEM,
        "--allowedTools",
        " ".join(_ALLOWED_TOOLS),
        "--disallowedTools",
        " ".join(_DENIED_TOOLS),
        "--max-budget-usd",
        str(max_budget_usd),
        prompt,
    ]


def make_b_claude_run_fn(
    *,
    model: str,
    run_subprocess: RunSubprocess,
    workdir_factory: WorkdirFactory,
    login: tuple[str, str],
    folder: str,
    max_budget_usd: float = 1.0,
    timeout_s: int = 600,
) -> Callable[[object, int, str], Trajectory]:
    """Build the per-trial claude -p B candidate driver. Same callback signature as
    make_b_chat_run_fn (task, run_index, save_name) -> Trajectory."""

    def run_fn(task, run_index: int, save_name: str) -> Trajectory:
        workdir = workdir_factory()
        try:
            user = next((m for m in task.input.messages if m.role == "user"), None)
            base_user = user.content if user is not None else ""
            prompt = render_b_prompt(
                base_user, save_name=save_name, login=login, folder=folder
            )
            argv = _build_b_claude_argv(
                model=model, prompt=prompt, max_budget_usd=max_budget_usd
            )
            env = _sanitized_env(os.environ)
            try:
                completed = run_subprocess(
                    argv, cwd=str(workdir), env=env, timeout=timeout_s
                )
            except subprocess.TimeoutExpired:
                return _env_invalid_trajectory(run_index, raw="timeout")
            if getattr(completed, "returncode", 0) != 0:
                return _env_invalid_trajectory(
                    run_index,
                    raw=(
                        f"stdout: {getattr(completed, 'stdout', '')}\n"
                        f"stderr: {getattr(completed, 'stderr', '')}"
                    ),
                )
            try:
                meta = parse_claude_result(completed.stdout)
            except ClaudeResultParseError as exc:
                return _env_invalid_trajectory(run_index, raw=str(exc))
            if meta.is_error:
                return _env_invalid_trajectory(run_index, raw="claude is_error")
            return Trajectory(
                turns=(),
                usage=Usage(
                    prompt_tokens=meta.prompt_tokens,
                    completion_tokens=meta.completion_tokens,
                    latency_s=0.0,
                ),
                run_index=run_index,
                stop_reason="completed_natural",
                rounds=meta.num_turns,
                tool_call_counts={},
                total_cost_usd=meta.total_cost_usd,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

    return run_fn
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/runners/test_b_candidate_claude.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/agent_eval_lab/runners/b_candidate_claude.py tests/runners/test_b_candidate_claude.py
uv run ruff check src/agent_eval_lab/runners/b_candidate_claude.py tests/runners/test_b_candidate_claude.py
git add src/agent_eval_lab/runners/b_candidate_claude.py tests/runners/test_b_candidate_claude.py
git commit -m "feat(b1-spike): add claude -p B candidate driver (num_turns + total_cost_usd)"
```

**Verification point:** `uv run pytest tests/runners/test_b_candidate_claude.py -q` green; success records turns+cost, nonzero-exit/timeout degrade to env-invalid (PROVIDER_ERROR), rendered prompt carries the save-name.

---

## Phase 7 — Config extension (spec §11.7 / §12)

### Task 7: Extend `CandidateConfig` with `folder`; confirm `url`/`password` reads

**Files:**
- Modify: `src/agent_eval_lab/experiments/evaluator_config.py`
- Test: locate the existing evaluator-config loader test (grep below) and append a `folder` assertion. If none exists, create `tests/experiments/test_evaluator_config.py`.

`CandidateConfig` already has `url`/`username`/`password`. Add `folder: str | None = None` (the save target; the owner chooses it before the live run — optional so existing configs/tests without it still load). The store relocation (§7) is an OPERATIONAL step recorded in the runbook (Task 11), not a code change — `[store] path` is already a config field.

- [ ] **Step 1: Locate the existing config test**

Run: `grep -rln "load_evaluator_config\|CandidateConfig" tests/`
Use the file it reports (likely `tests/experiments/test_evaluator_config.py`). If absent, create it. Read it first to mirror its TOML-fixture style.

- [ ] **Step 2: Write the failing test**

Append (adapt the fixture-building helper to the existing test's style — it likely writes a temp `evaluator.toml`):

```python
def test_candidate_folder_is_read_when_present(tmp_path) -> None:
    from agent_eval_lab.experiments.evaluator_config import load_evaluator_config

    toml = tmp_path / "evaluator.toml"
    toml.write_text(
        """
[store]
path = "/tmp/store"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "/tmp/skill.md"
[candidate]
url = "https://lab/MicroStrategyLibrary/app"
username = "bxu"
password = "secret"
folder = "/Candidate/bxu"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""",
        encoding="utf-8",
    )
    cfg = load_evaluator_config(toml)
    assert cfg.candidate.folder == "/Candidate/bxu"
    assert cfg.candidate.url == "https://lab/MicroStrategyLibrary/app"
    assert cfg.candidate.password == "secret"


def test_candidate_folder_defaults_to_none_when_absent(tmp_path) -> None:
    from agent_eval_lab.experiments.evaluator_config import load_evaluator_config

    toml = tmp_path / "evaluator.toml"
    toml.write_text(
        """
[store]
path = "/tmp/store"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "/tmp/skill.md"
[candidate]
username = "bxu"
password = "secret"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""",
        encoding="utf-8",
    )
    cfg = load_evaluator_config(toml)
    assert cfg.candidate.folder is None
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/experiments/test_evaluator_config.py -q` (or the located path)
Expected: FAIL — `AttributeError: 'CandidateConfig' object has no attribute 'folder'`.

- [ ] **Step 4: Add `folder` to `CandidateConfig` + the loader**

In `evaluator_config.py`, add the field to `CandidateConfig` (after `password`):

```python
    url: str | None = None
    username: str
    password: str
    folder: str | None = None
```

And in `load_evaluator_config`, set it from the candidate section (optional read, mirroring `url`):

```python
        candidate=CandidateConfig(
            url=str(candidate_sec["url"]) if "url" in candidate_sec else None,
            username=str(_require_key(candidate_sec, "username", "candidate")),
            password=str(_require_key(candidate_sec, "password", "candidate")),
            folder=str(candidate_sec["folder"]) if "folder" in candidate_sec else None,
        ),
```

NOTE: `CandidateConfig` is `kw_only=True`, so a defaulted field after non-defaulted ones is legal.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/experiments/test_evaluator_config.py -q`
Expected: PASS — new tests pass AND existing config tests still pass.

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/agent_eval_lab/experiments/evaluator_config.py tests/experiments/test_evaluator_config.py
uv run ruff check src/agent_eval_lab/experiments/evaluator_config.py tests/experiments/test_evaluator_config.py
git add src/agent_eval_lab/experiments/evaluator_config.py tests/experiments/test_evaluator_config.py
git commit -m "feat(b1-spike): read [candidate] folder for the B save target"
```

**Verification point:** `uv run pytest tests/experiments/test_evaluator_config.py -q` green; `folder` reads when present, defaults to `None`.

---

## Phase 8 — `b_scoring.py` verdict-sheet emitter (spec §11.9 / §5)

### Task 8: `emit_verdict_sheet(trials) -> (markdown, csv)`

**Files:**
- Create: `src/agent_eval_lab/reports/b_scoring.py`
- Test: `tests/reports/test_b_scoring.py`

The verdict sheet: the definition-match checklist on top, one row per trial (model, arm, trial, instructed save-name, folder, stop_reason — `max_rounds` flagged as `(censored)`, rounds, tokens, cost, wall-time, candidate final-message excerpt, transcript path) + a blank verdict column for the owner. PURE. Distinct from the blind annotation packet — the owner inspects the live MSTR object, so the sheet is not blind.

- [ ] **Step 1: Write the failing tests**

```python
from agent_eval_lab.records.b_trial import BTrial
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.b_scoring import emit_verdict_sheet


def _trial(*, task_id, save_name, stop_reason, rounds, max_rounds_bound=False):
    return BTrial(
        run_uid=f"c__{task_id}__0000",
        condition_id="dashscope:qwen3.7-max",
        task_id=task_id,
        save_name=save_name,
        folder="/Candidate/bxu",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=2.0),
            run_index=0,
            stop_reason=stop_reason,
            rounds=rounds,
            wall_time_s=12.5,
            max_rounds_bound=max_rounds_bound,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_verdict_sheet_carries_checklist_and_blank_verdict_column() -> None:
    md, csv = emit_verdict_sheet(
        [_trial(task_id="b-b1-noskill", save_name="s0", stop_reason="completed_natural", rounds=7)]
    )
    # The definition-match checklist R1..R5 is at the top of the markdown sheet.
    for marker in ("R1", "R2", "R3", "R4", "R5"):
        assert marker in md
    # One row per trial, a blank verdict column header, and the instructed save-name.
    assert "verdict" in md.lower()
    assert "s0" in md
    assert "b-b1-noskill" in md
    # CSV header includes save_name + a blank verdict column.
    header = csv.splitlines()[0]
    assert "save_name" in header
    assert "verdict" in header


def test_verdict_sheet_flags_max_rounds_censored_distinctly() -> None:
    md, csv = emit_verdict_sheet(
        [
            _trial(
                task_id="b-b1-noskill",
                save_name="s_capped",
                stop_reason="max_rounds",
                rounds=50,
                max_rounds_bound=True,
            )
        ]
    )
    # A max_rounds cap is surfaced as a censored task-failure, distinct from a clean stop.
    assert "censored" in md.lower()
    assert "max_rounds (censored)" in md or "max_rounds(censored)" in md.replace(" ", "")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/reports/test_b_scoring.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.reports.b_scoring`.

- [ ] **Step 3: Implement `reports/b_scoring.py`**

```python
"""PURE: the B-1 verdict sheet (spec §5 / §11.9).

emit_verdict_sheet(trials) -> (markdown, csv): the definition-match checklist on
top, one evidence row per trial (model, arm, instructed save-name, folder,
stop_reason — max_rounds flagged distinctly as (censored), rounds, tokens, cost*,
wall-time, transcript path) + a BLANK verdict column the owner fills. Distinct from
the blind annotation packet: the owner inspects the live MSTR object, so the sheet
carries the save-name + folder (not blind). *cost is left blank here — it is
derived at report time from tokens x pricing (chat) / total_cost_usd (claude); the
sheet shows tokens + any per-run total_cost_usd for at-a-glance review.
"""

from __future__ import annotations

from collections.abc import Sequence

from agent_eval_lab.records.b_trial import BTrial

_CHECKLIST = (
    "## B-1 definition-match checklist (owner verdict: PASS | FAIL | INVALID)\n\n"
    "A trial PASSES iff all five hold:\n"
    "- **R1** — an object exists, saved under the instructed unique name, in the candidate folder.\n"
    "- **R2** — source dataset = SAPBW > AV_TUTO > Query_CharacteristicValue_Mandatory.\n"
    "- **R3** — Rows include Years Hierarchy AND Region.\n"
    "- **R4** — Columns include Cost.\n"
    "- **R5** — the mandatory prompt is answered South and the report renders the prompted result.\n\n"
    "PASS = R1 ∧ R2 ∧ R3 ∧ R4 ∧ R5; otherwise FAIL. INVALID = env/provider failure "
    "(auto-tagged; owner may override).\n"
)

_COLUMNS = (
    "model",
    "arm",
    "save_name",
    "folder",
    "stop_reason",
    "rounds",
    "prompt_tokens",
    "completion_tokens",
    "total_cost_usd",
    "wall_time_s",
    "verdict",
)


def _stop_display(trial: BTrial) -> str:
    """A max_rounds (or safety_cap) cap is a CENSORED task-failure — flag it
    distinctly so the owner does not read it as a clean completion (spec §6.3)."""
    sr = trial.trajectory.stop_reason
    if sr in ("max_rounds", "safety_cap"):
        return f"{sr} (censored)"
    return sr


def _row_values(trial: BTrial) -> tuple[str, ...]:
    t = trial.trajectory
    return (
        trial.condition_id,
        trial.task_id,
        trial.save_name,
        trial.folder,
        _stop_display(trial),
        str(t.rounds),
        str(t.usage.prompt_tokens),
        str(t.usage.completion_tokens),
        "" if t.total_cost_usd is None else f"{t.total_cost_usd:.4f}",
        f"{t.wall_time_s:.1f}",
        "",  # blank verdict — the owner fills PASS | FAIL | INVALID
    )


def emit_verdict_sheet(trials: Sequence[BTrial]) -> tuple[str, str]:
    """Return (markdown, csv). PURE — no I/O; the CLI writes the strings to disk."""
    rows = [_row_values(t) for t in trials]

    header = "| " + " | ".join(_COLUMNS) + " |"
    sep = "| " + " | ".join("---" for _ in _COLUMNS) + " |"
    body = "\n".join("| " + " | ".join(r) + " |" for r in rows)
    markdown = f"{_CHECKLIST}\n## Evidence rows\n\n{header}\n{sep}\n{body}\n"

    csv_lines = [",".join(_COLUMNS)] + [",".join(r) for r in rows]
    csv = "\n".join(csv_lines) + "\n"
    return markdown, csv
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/reports/test_b_scoring.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/agent_eval_lab/reports/b_scoring.py tests/reports/test_b_scoring.py
uv run ruff check src/agent_eval_lab/reports/b_scoring.py tests/reports/test_b_scoring.py
git add src/agent_eval_lab/reports/b_scoring.py tests/reports/test_b_scoring.py
git commit -m "feat(b1-spike): add pure verdict-sheet emitter (checklist + evidence rows)"
```

**Verification point:** `uv run pytest tests/reports/test_b_scoring.py -q` green; checklist + blank verdict column present, `max_rounds (censored)` flagged distinctly.

---

## Phase 9 — `run-b` CLI command (spec §11.8 / §5)

### Task 9: `_run_b_command` + parser + `main` dispatch

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (add `_run_b_command`, parser, dispatch)
- Test: `tests/cli/test_run_b.py`

One model per invocation, `--arm {noskill,skill,both}` (default `both`); mirrors `_run_f_command`. Incremental `trials-b-<slug>-<task_id>.jsonl` writes (`BTrial`, not `RunResult`) + a `.void.json` sidecar + the verdict sheet. Auth/quota fail-fast (HTTP 401/403) via `provider_auth_quota_status`; `httpx.TransportError` handling. The candidate-driver factory is injected (`candidate_run_fn_factory=None`) so the test runs with a fake, never a live provider/MSTR — exactly like `_run_f_claude_baseline_command(args, *, run_fn_factory=None)`.

- [ ] **Step 1: Write the failing test (injected candidate factory; no provider, no MSTR)**

```python
import argparse
import json
from pathlib import Path

from agent_eval_lab.records.trajectory import Trajectory, Usage


def _ok(run_index):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
        run_index=run_index,
        stop_reason="completed_natural",
        rounds=5,
        wall_time_s=8.0,
    )


def _write_cfg(tmp_path: Path) -> Path:
    toml = tmp_path / "evaluator.toml"
    toml.write_text(
        """
[store]
path = "{store}"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "{skill}"
[candidate]
url = "https://lab/app"
username = "bxu"
password = "secret"
folder = "/Candidate/bxu"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""".format(store=tmp_path / "store", skill=tmp_path / "skill.md"),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# stripped skill\n", encoding="utf-8")
    return toml


def test_run_b_writes_trials_and_verdict_sheet_both_arms(tmp_path, monkeypatch) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    # The candidate factory returns a fake run_fn (no provider, no MSTR).
    def fake_factory(*, arm, condition_id, folder, login):
        def run_fn(task, run_index, save_name):
            return _ok(run_index)

        return run_fn

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0

    # One trials artifact per arm (task_id), BTrial JSONL (no "grade" key).
    noskill = list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    skill = list(out.glob("trials-b-*-b-b1-skill.jsonl"))
    assert len(noskill) == 1 and len(skill) == 1
    line = json.loads(noskill[0].read_text().splitlines()[0])
    assert "grade" not in line
    assert line["save_name"].endswith("__b-b1-noskill__0000")
    # A void sidecar + the verdict sheet (md + csv) exist.
    assert (noskill[0].with_suffix(".void.json")).exists()
    assert list(out.glob("b1-verdict-sheet-*.md"))
    assert list(out.glob("b1-verdict-sheet-*.csv"))


def test_run_b_single_arm(tmp_path) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    def fake_factory(*, arm, condition_id, folder, login):
        return lambda task, run_index, save_name: _ok(run_index)

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="noskill",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0
    assert list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    assert not list(out.glob("trials-b-*-b-b1-skill.jsonl"))
```

(If `build_b_tasks` requires a golden file + skill path on disk, the fixture writes the skill; the golden_dir gate is for `b1_oracle` which the live path never uses. Pass `golden_dir`/`strategy_test_path` such that `build_b_tasks` succeeds — read `build_b1_verification` to confirm what it needs; if it needs a golden JSON, write a minimal `b1-golden.json` into the store fixture, OR have `_run_b_command` build the arm tasks WITHOUT the oracle. PREFERRED: `_run_b_command` builds the two arm Tasks via a thin local helper that only needs the system/user messages + the skill text — the live path never grades, so it does not need `build_b1_verification`. See Step 3.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/cli/test_run_b.py -q`
Expected: FAIL — `AttributeError: module 'agent_eval_lab.cli' has no attribute '_run_b_command'`.

- [ ] **Step 3: Implement `_run_b_command` + a default candidate factory + the arm-task builder**

Add to `cli.py`. The default factory (used by real runs) builds the chat driver via `make_b_chat_run_fn` (or the claude driver when `--driver claude`); tests inject `candidate_run_fn_factory`. Build the two arm Tasks without requiring the oracle golden (the live path never grades). The arm tasks reuse `b_tasks._SYSTEM` / `_B1_USER` + the stripped skill for the skill arm.

`_make_live_b_task` is grounded: `Task.verification` is non-optional (`schema.py:213`), and the live path never reads it, so it uses `AllOf(specs=())` (the minimal valid `VerificationSpec`, `schema.py:83-85`). It mirrors `b_tasks._task` (capability `browser_mstr`, `available_tools=("bash",)`, `initial_state={"task_key": "B-1"}`, `TaskMetadata` like `b_tasks._task`).

```python
_B_ARMS = {"noskill": "b-b1-noskill", "skill": "b-b1-skill"}


def _make_live_b_task(task_id: str, messages: tuple) -> Task:
    """A B-1 arm Task for the LIVE path. verification is a minimal AllOf(specs=())
    the live path never reads (Task.verification is non-optional; B grades by owner
    verdict, not an automated spec). Mirrors datasets.b_tasks._task otherwise."""
    from agent_eval_lab.tasks.schema import AllOf, TaskInput, TaskMetadata

    return Task(
        id=task_id,
        capability="browser_mstr",
        input=TaskInput(messages=messages, available_tools=("bash",)),
        verification=AllOf(specs=()),
        metadata=TaskMetadata(
            split="held_out",
            version="b-domain-v1",
            provenance="source spec §4.3 exemplar B-1 (Tutorial Project)",
        ),
        initial_state={"task_key": "B-1"},
    )


def _build_b_arm_tasks(cfg) -> dict:
    """Build the two B-1 arm Tasks (noskill, skill) for the LIVE path — no oracle
    golden required (the spike grades by owner verdict, not an automated spec). The
    skill arm injects the stripped strategy-test skill into the system prompt."""
    from agent_eval_lab.datasets.b_tasks import _B1_USER, _SYSTEM
    from agent_eval_lab.datasets.skill_loader import load_stripped_skill
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.runners.prompt import apply_system_prompt

    base_messages = (
        MessageTurn(role="system", content=_SYSTEM),
        MessageTurn(role="user", content=_B1_USER),
    )
    skill_text = load_stripped_skill(Path(cfg.skill.strategy_test_path))
    skill_messages = apply_system_prompt(base_messages, f"{_SYSTEM}\n\n{skill_text}")
    return {
        "b-b1-noskill": _make_live_b_task("b-b1-noskill", base_messages),
        "b-b1-skill": _make_live_b_task("b-b1-skill", skill_messages),
    }
```

Then the command:

```python
def _run_b_command(args, candidate_run_fn_factory=None) -> int:
    """EDGE: run ONE model over the B-1 arms LIVE (spec §11.8). Standalone per
    model (run-f parity), NOT the run-m1 orchestrator. Writes a grade-less
    trials-b-<slug>-<arm>.jsonl per arm (BTrial, ADR-0021) + a .void.json sidecar +
    the verdict sheet for the owner. Live MSTR + provider are reached only by the
    REAL candidate factory; tests inject candidate_run_fn_factory.

    Shared-account note (§7): arms run SEQUENTIALLY on the single least-priv bxu
    login; isolation is by the unique per-trial save-name."""
    from agent_eval_lab.reports.b_scoring import emit_verdict_sheet
    from agent_eval_lab.runners.b_live import run_b_arm

    cfg = load_evaluator_config(args.evaluator_config)
    config = PROVIDERS[args.provider]
    if args.model:
        config = replace(config, model_id=args.model)
    cond = condition_id(config)

    arms = ["noskill", "skill"] if args.arm == "both" else [args.arm]
    arm_tasks = _build_b_arm_tasks(cfg)

    login = (cfg.candidate.url or "", cfg.candidate.username)
    folder = cfg.candidate.folder or ""

    factory = candidate_run_fn_factory or _real_b_candidate_factory(
        cfg=cfg, config=config, args=args, cond=cond, login=login, folder=folder
    )

    args.out.mkdir(parents=True, exist_ok=True)
    all_trials = []
    void_arms: list[str] = []
    aborted = False
    try:
        for arm in arms:  # SEQUENTIAL (shared bxu login, §7)
            task = arm_tasks[_B_ARMS[arm]]
            run_fn = factory(arm=arm, condition_id=cond, folder=folder, login=login)
            outcome = run_b_arm(
                task=task,
                condition_id=cond,
                folder=folder,
                candidate_run_fn=run_fn,
                k_valid=cfg.runner.k_valid,
                max_invalid_rate=cfg.runner.max_invalid_rate,
            )
            path = args.out / f"trials-b-{_slug(cond)}-{task.id}.jsonl"
            with path.open("w") as fh:
                fh.write(
                    "".join(
                        json.dumps(b_trial_to_dict(t)) + "\n" for t in outcome.all_trials
                    )
                )
            path.with_suffix(".void.json").write_text(
                json.dumps({"void": outcome.void, "arm": task.id}), encoding="utf-8"
            )
            all_trials.extend(outcome.all_trials)
            if outcome.void:
                void_arms.append(task.id)
                print(
                    f"[void] B arm {task.id}: fewer than k clean trials — provider "
                    "errors masked (env-invalid); excluded (D34).",
                    file=sys.stderr,
                )
            # Fail-fast on an account-global auth/quota block (HTTP 401/403).
            block = next(
                (
                    s
                    for t in outcome.all_trials
                    if (s := provider_auth_quota_status(t.trajectory)) is not None
                ),
                None,
            )
            if block is not None:
                print(
                    f"error: provider auth/quota rejection (HTTP {block}) on arm "
                    f"{task.id!r} — aborting before more dead trials (401/403 is an "
                    "account-global block). Fix the key/quota and retry.",
                    file=sys.stderr,
                )
                aborted = True
                break
    except httpx.TransportError as exc:
        print(
            f"error: cannot reach provider {config.id!r} at {config.base_url} "
            f"({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        aborted = True
    # Emit the verdict sheet over whatever trials were recorded (even on abort).
    md, csv = emit_verdict_sheet(all_trials)
    (args.out / f"b1-verdict-sheet-{_slug(cond)}.md").write_text(md, encoding="utf-8")
    (args.out / f"b1-verdict-sheet-{_slug(cond)}.csv").write_text(csv, encoding="utf-8")
    if aborted:
        return 1
    print(args.out / f"b1-verdict-sheet-{_slug(cond)}.md")
    return 0
```

Add the import at cli.py top: `from agent_eval_lab.records.b_trial import b_trial_to_dict`.

Define `_real_b_candidate_factory(*, cfg, config, args, cond, login, folder)` returning a `factory(*, arm, condition_id, folder, login) -> run_fn`. For `args.driver == "chat"` it builds an `httpx.Client` (trust_env=False, proxy=`resolve_proxy(config, os.environ)`) once and returns `make_b_chat_run_fn(...)` per arm with `workdir_root = Path(cfg.store.path) / "b-work"`. For `args.driver == "claude"` it returns `make_b_claude_run_fn(model=args.model or config.model_id, run_subprocess=subprocess.run, workdir_factory=lambda: Path(tempfile.mkdtemp()), login=login, folder=folder)`. (Tests never reach this — they inject the factory.)

- [ ] **Step 4: Wire the parser + dispatch**

In `_build_parser`, after the `run-f` block, add:

```python
    rb = subparsers.add_parser(
        "run-b",
        help="run ONE model over the B-1 MSTR arms LIVE (human-scored spike) — "
        "writes grade-less BTrials + a verdict sheet for the owner",
    )
    rb.add_argument("--provider", required=True, choices=sorted(PROVIDERS))
    rb.add_argument("--model", help="override the provider's default model id")
    rb.add_argument("--evaluator-config", required=True, type=Path, metavar="TOML")
    rb.add_argument("--out", type=Path, default=Path("reports"))
    rb.add_argument("--arm", choices=["noskill", "skill", "both"], default="both")
    rb.add_argument("--driver", choices=["chat", "claude"], default="chat")
    rb.add_argument("--temperature", type=float, default=0.0)
    rb.add_argument("--max-tokens", type=int, default=4096)
```

In `main`, after the `run-f` dispatch:

```python
    if args.command == "run-b":
        return _run_b_command(args)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/cli/test_run_b.py -q`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/agent_eval_lab/cli.py tests/cli/test_run_b.py
uv run ruff check src/agent_eval_lab/cli.py tests/cli/test_run_b.py
git add src/agent_eval_lab/cli.py tests/cli/test_run_b.py
git commit -m "feat(b1-spike): add run-b CLI (per-model arms, BTrial writes, verdict sheet)"
```

**Verification point:** `uv run pytest tests/cli/test_run_b.py -q` green; `trials-b-*-<arm>.jsonl` carries grade-less BTrials, `.void.json` + verdict-sheet `.md`/`.csv` emitted, single-arm works.

---

## Phase 10 — `b_report.py` + `report-b` CLI (spec §11.10 / §5 / §6)

### Task 10a: `report_b(trials, verdicts) -> BReport` (pure grade build + metrics)

**Files:**
- Create: `src/agent_eval_lab/reports/b_report.py`
- Test: `tests/reports/test_b_report.py`

Join each `BTrial` with its owner verdict (`PASS|FAIL|INVALID`) to build a per-(model, arm) result PURELY: headline `pass_at_1` (per-trial pass rate over valid trials), secondary `pass_pow_3` (all-k-pass), valid/invalid/void counts, mean+median rounds/tokens/cost/wall-time, plus the descriptive skill delta on `pass_at_1` (skill − noskill) per model. `claude -p` efficiency is rendered on its own axis ("turns (Claude Code)" / "USD (subscription-equiv)"), never pooled with chat rounds/cost. Cost: chat → tokens × pricing; claude → `total_cost_usd`.

- [ ] **Step 1: Write the failing tests**

```python
from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.b_trial import BTrial
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.b_report import report_b


def _trial(*, condition_id, task_id, run_index, rounds, pt=100, ct=50, cost=None):
    return BTrial(
        run_uid=f"{condition_id}__{task_id}__{run_index:04d}",
        condition_id=condition_id,
        task_id=task_id,
        save_name=f"{condition_id}-{task_id}-{run_index}",
        folder="/f",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=pt, completion_tokens=ct, latency_s=1.0),
            run_index=run_index,
            stop_reason="completed_natural",
            rounds=rounds,
            wall_time_s=10.0,
            total_cost_usd=cost,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_report_b_builds_pass_at_1_and_skill_delta() -> None:
    cond = "dashscope:qwen3.7-max"
    trials = [
        _trial(condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=5)
        for i in range(3)
    ] + [
        _trial(condition_id=cond, task_id="b-b1-skill", run_index=i, rounds=4)
        for i in range(3)
    ]
    verdicts = {
        # noskill: 2/3 pass; skill: 3/3 pass -> skill delta = +1/3.
        f"{cond}__b-b1-noskill__0000": "PASS",
        f"{cond}__b-b1-noskill__0001": "PASS",
        f"{cond}__b-b1-noskill__0002": "FAIL",
        f"{cond}__b-b1-skill__0000": "PASS",
        f"{cond}__b-b1-skill__0001": "PASS",
        f"{cond}__b-b1-skill__0002": "PASS",
    }
    report = report_b(
        trials, verdicts, pricing={cond: TokenPrice(input_per_mtok=1.0, output_per_mtok=2.0)}
    )
    rows = {(r.condition_id, r.arm): r for r in report.rows}
    assert rows[(cond, "b-b1-noskill")].pass_at_1 == 2 / 3
    assert rows[(cond, "b-b1-skill")].pass_at_1 == 1.0
    assert rows[(cond, "b-b1-noskill")].pass_pow_3 is False  # not all 3 passed
    assert rows[(cond, "b-b1-skill")].pass_pow_3 is True
    # Skill delta on pass_at_1 (skill - noskill), per model.
    assert report.skill_delta[cond] == 1.0 - (2 / 3)
    # Chat cost is tokens x pricing (3 noskill trials: 3*(100*1 + 50*2)/1e6).
    assert rows[(cond, "b-b1-noskill")].cost_usd > 0


def test_report_b_invalid_verdict_excluded_from_pass_at_1() -> None:
    cond = "deepseek:deepseek-v4-pro"
    trials = [
        _trial(condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=5)
        for i in range(3)
    ]
    verdicts = {
        f"{cond}__b-b1-noskill__0000": "PASS",
        f"{cond}__b-b1-noskill__0001": "INVALID",  # owner overrode to INVALID
        f"{cond}__b-b1-noskill__0002": "FAIL",
    }
    report = report_b(trials, verdicts, pricing={})
    row = next(r for r in report.rows if r.arm == "b-b1-noskill")
    # INVALID is masked: pass_at_1 over the 2 VALID verdicts = 1/2.
    assert row.valid == 2
    assert row.invalid == 1
    assert row.pass_at_1 == 0.5


def test_report_b_claude_efficiency_on_its_own_axis() -> None:
    cond = "claude-cli:claude-sonnet-4-6"
    trials = [
        _trial(condition_id=cond, task_id="b-b1-noskill", run_index=i, rounds=6, cost=0.03)
        for i in range(3)
    ]
    verdicts = {f"{cond}__b-b1-noskill__{i:04d}": "PASS" for i in range(3)}
    report = report_b(trials, verdicts, pricing={})
    row = next(r for r in report.rows if r.arm == "b-b1-noskill")
    # claude rows are flagged so the renderer never pools turns/USD with chat rounds.
    assert row.is_subprocess_driver is True
    # cost comes from total_cost_usd (3 * 0.03), not tokens x pricing.
    assert abs(row.cost_usd - 0.09) < 1e-9
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/reports/test_b_report.py -q`
Expected: FAIL — `ModuleNotFoundError: agent_eval_lab.reports.b_report`.

- [ ] **Step 3: Implement `reports/b_report.py`**

```python
"""PURE: join owner verdicts with grade-less BTrials -> per-(model, arm) B-1
metrics (spec §5 / §6 / ADR-0021).

report_b(trials, verdicts, pricing) constructs the grade from the owner verdict at
report time — never a fabricated run-time GradeResult. Per (condition, arm):
headline pass_at_1 (per-trial pass rate over VALID verdicts), secondary pass_pow_3
(all-k pass), valid/invalid counts, mean/median rounds/tokens/cost/wall-time; plus
the descriptive skill delta on pass_at_1 (skill - noskill) per model. A condition
whose id is a subprocess (claude-cli:*) driver is FLAGGED (is_subprocess_driver) so
the renderer keeps its turns/USD on a separate efficiency axis (decision 5) and its
cost comes from total_cost_usd, not tokens x pricing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, median

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.b_trial import BTrial

OwnerVerdict = str  # "PASS" | "FAIL" | "INVALID"

_NOSKILL = "b-b1-noskill"
_SKILL = "b-b1-skill"


def _is_subprocess_driver(condition_id: str) -> bool:
    """claude -p is a subprocess driver — its efficiency (turns / subscription-USD)
    rides a SEPARATE axis, never pooled with chat-model rounds/cost (decision 5)."""
    return condition_id.startswith("claude-cli:")


@dataclass(frozen=True, kw_only=True)
class BReportRow:
    condition_id: str
    arm: str
    valid: int  # trials with a PASS/FAIL verdict (INVALID excluded)
    invalid: int  # trials whose verdict is INVALID (or missing)
    pass_at_1: float  # headline: passes / valid
    pass_pow_3: bool  # secondary: valid >= 3 AND all valid passed
    mean_rounds: float
    median_rounds: float
    mean_tokens: float
    cost_usd: float  # chat: tokens x pricing; claude: sum total_cost_usd
    mean_wall_time_s: float
    is_subprocess_driver: bool


@dataclass(frozen=True, kw_only=True)
class BReport:
    rows: tuple[BReportRow, ...]
    skill_delta: Mapping[str, float]  # condition_id -> pass_at_1(skill) - pass_at_1(noskill)


def _verdict_for(trial: BTrial, verdicts: Mapping[str, OwnerVerdict]) -> str:
    """The owner verdict for a trial, defaulting a missing one to INVALID (the
    runner auto-tagged trial is invalid; a missing owner verdict is treated as
    INVALID, never a silent FAIL — anti-silent discipline)."""
    if trial.invalid:
        return "INVALID"
    return verdicts.get(trial.run_uid, "INVALID")


def _cost(trials: Sequence[BTrial], *, condition_id: str, pricing: Mapping[str, TokenPrice]) -> float:
    if _is_subprocess_driver(condition_id):
        return sum((t.trajectory.total_cost_usd or 0.0) for t in trials)
    price = pricing.get(condition_id)
    if price is None:
        return 0.0
    pt = sum(t.trajectory.usage.prompt_tokens for t in trials)
    ct = sum(t.trajectory.usage.completion_tokens for t in trials)
    return (pt * price.input_per_mtok + ct * price.output_per_mtok) / 1_000_000


def _row(condition_id: str, arm: str, trials: Sequence[BTrial], verdicts, pricing) -> BReportRow:
    scored = [(t, _verdict_for(t, verdicts)) for t in trials]
    valid = [(t, v) for t, v in scored if v in ("PASS", "FAIL")]
    passes = sum(1 for _, v in valid if v == "PASS")
    n_valid = len(valid)
    valid_trials = [t for t, _ in valid]
    rounds = [t.trajectory.rounds for t in valid_trials] or [0]
    tokens = [
        t.trajectory.usage.prompt_tokens + t.trajectory.usage.completion_tokens
        for t in valid_trials
    ] or [0]
    walls = [t.trajectory.wall_time_s for t in valid_trials] or [0.0]
    return BReportRow(
        condition_id=condition_id,
        arm=arm,
        valid=n_valid,
        invalid=len(trials) - n_valid,
        pass_at_1=(passes / n_valid) if n_valid else 0.0,
        pass_pow_3=(n_valid >= 3 and passes == n_valid),
        mean_rounds=mean(rounds),
        median_rounds=median(rounds),
        mean_tokens=mean(tokens),
        cost_usd=_cost(valid_trials, condition_id=condition_id, pricing=pricing),
        mean_wall_time_s=mean(walls),
        is_subprocess_driver=_is_subprocess_driver(condition_id),
    )


def report_b(
    trials: Sequence[BTrial],
    verdicts: Mapping[str, OwnerVerdict],
    *,
    pricing: Mapping[str, TokenPrice],
) -> BReport:
    """Build the B-1 report. PURE — no I/O. `verdicts` maps run_uid -> owner verdict."""
    by_key: dict[tuple[str, str], list[BTrial]] = {}
    for t in trials:
        by_key.setdefault((t.condition_id, t.task_id), []).append(t)
    rows = tuple(
        _row(cond, arm, group, verdicts, pricing)
        for (cond, arm), group in sorted(by_key.items())
    )
    # Skill delta on pass_at_1 (skill - noskill) per model, where both arms exist.
    pa1: dict[tuple[str, str], float] = {(r.condition_id, r.arm): r.pass_at_1 for r in rows}
    conditions = sorted({r.condition_id for r in rows})
    skill_delta = {
        c: pa1[(c, _SKILL)] - pa1[(c, _NOSKILL)]
        for c in conditions
        if (c, _SKILL) in pa1 and (c, _NOSKILL) in pa1
    }
    return BReport(rows=rows, skill_delta=skill_delta)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/reports/test_b_report.py -q`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
uv run ruff format src/agent_eval_lab/reports/b_report.py tests/reports/test_b_report.py
uv run ruff check src/agent_eval_lab/reports/b_report.py tests/reports/test_b_report.py
git add src/agent_eval_lab/reports/b_report.py tests/reports/test_b_report.py
git commit -m "feat(b1-spike): add pure report_b (pass_at_1 headline + skill delta + claude axis)"
```

### Task 10b: `report-b` CLI command

**Files:**
- Modify: `src/agent_eval_lab/cli.py` (add `_run_report_b`, parser, dispatch)
- Test: `tests/cli/test_report_b.py`

Pure consumer: reads `trials-b-*.jsonl` (BTrials) + an owner-verdicts JSON (`{run_uid: "PASS"|"FAIL"|"INVALID"}`) + the pricing snapshot → writes a markdown report. Mirrors `report-m1`'s pure-consumer shape.

- [ ] **Step 1: Write the failing test**

```python
import argparse
import json
from pathlib import Path

from agent_eval_lab.records.b_trial import BTrial, b_trial_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _trial(cond, arm, i):
    return BTrial(
        run_uid=f"{cond}__{arm}__{i:04d}",
        condition_id=cond,
        task_id=arm,
        save_name=f"{cond}-{arm}-{i}",
        folder="/f",
        trajectory=Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
            run_index=i,
            stop_reason="completed_natural",
            rounds=5,
            wall_time_s=9.0,
        ),
        invalid=False,
        invalid_reason=None,
    )


def test_report_b_cli_joins_trials_and_verdicts(tmp_path) -> None:
    from agent_eval_lab import cli

    cond = "dashscope:qwen3.7-max"
    trials_path = tmp_path / "trials-b-x-b-b1-noskill.jsonl"
    trials_path.write_text(
        "".join(
            json.dumps(b_trial_to_dict(_trial(cond, "b-b1-noskill", i))) + "\n"
            for i in range(3)
        ),
        encoding="utf-8",
    )
    verdicts = tmp_path / "verdicts.json"
    verdicts.write_text(
        json.dumps(
            {
                f"{cond}__b-b1-noskill__0000": "PASS",
                f"{cond}__b-b1-noskill__0001": "PASS",
                f"{cond}__b-b1-noskill__0002": "FAIL",
            }
        ),
        encoding="utf-8",
    )
    prices = tmp_path / "pricing.json"
    prices.write_text(
        json.dumps(
            {"snapshot_date": "2026-06-17", "prices": {cond: {"input_per_mtok": 1.0, "output_per_mtok": 2.0}}}
        ),
        encoding="utf-8",
    )
    out = tmp_path / "B1-report.md"
    args = argparse.Namespace(
        trials=[trials_path], verdicts=verdicts, prices=prices, out=out
    )
    rc = cli._run_report_b(args)
    assert rc == 0
    text = out.read_text()
    assert "pass_at_1" in text or "pass@1" in text.lower()
    assert "0.667" in text or "2/3" in text  # noskill pass_at_1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/cli/test_report_b.py -q`
Expected: FAIL — `AttributeError: module 'agent_eval_lab.cli' has no attribute '_run_report_b'`.

- [ ] **Step 3: Implement `_run_report_b` + a thin renderer**

Add a `render_b_report(report) -> str` to `reports/b_report.py` (pure markdown), and `_run_report_b` to `cli.py`. Reuse `_load_prices` (already in cli.py) for the pricing map.

Add to `reports/b_report.py`:

```python
def render_b_report(report: BReport) -> str:
    """Render the B-1 report markdown. PURE. claude -p efficiency is on its own
    axis (turns (Claude Code) / USD (subscription-equiv)); B-1 is a ONE-TASK
    contingency (never a CI labelled as bootstrap)."""
    lines = [
        "# B-1 Live Spike report (human-scored — owner verdict)",
        "",
        "> B-1 is a ONE-TASK contingency (point summary, not a cluster bootstrap CI).",
        "",
        "| model | arm | valid | invalid | pass_at_1 | pass_pow_3 | mean_rounds | "
        "cost_usd | efficiency_axis |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.rows:
        axis = "turns (Claude Code) / USD (subscription-equiv)" if r.is_subprocess_driver else "rounds / token-USD"
        lines.append(
            f"| {r.condition_id} | {r.arm} | {r.valid} | {r.invalid} | "
            f"{r.pass_at_1:.3f} | {r.pass_pow_3} | {r.mean_rounds:.1f} | "
            f"{r.cost_usd:.4f} | {axis} |"
        )
    lines += ["", "## Skill delta on pass_at_1 (skill − noskill)", ""]
    for cond, delta in sorted(report.skill_delta.items()):
        lines.append(f"- {cond}: {delta:+.3f}")
    return "\n".join(lines) + "\n"
```

Add to `cli.py`:

```python
def _run_report_b(args) -> int:
    """PURE consumer: trials-b-*.jsonl (BTrial) + owner-verdicts JSON + pricing ->
    the B-1 report. Mirrors report-m1's pure shape (spec §11.10)."""
    from agent_eval_lab.records.b_trial import b_trial_from_dict
    from agent_eval_lab.reports.b_report import render_b_report, report_b

    trials = []
    for path in args.trials:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if line.strip():
                trials.append(b_trial_from_dict(json.loads(line)))
    verdicts = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    _, prices = _load_prices(args.prices)
    report = report_b(trials, verdicts, pricing=prices)
    Path(args.out).write_text(render_b_report(report), encoding="utf-8")
    print(args.out)
    return 0
```

- [ ] **Step 4: Wire the parser + dispatch**

In `_build_parser`, after the `run-b` block:

```python
    rpb = subparsers.add_parser(
        "report-b",
        help="join owner verdicts with recorded B-1 trials into the spike report (pure)",
    )
    rpb.add_argument(
        "--trials", nargs="+", type=Path, required=True,
        help="one or more trials-b-*.jsonl artifacts (BTrial JSONL)",
    )
    rpb.add_argument("--verdicts", type=Path, required=True, metavar="JSON",
                     help="owner verdicts: {run_uid: PASS|FAIL|INVALID}")
    rpb.add_argument("--prices", type=Path, required=True, metavar="JSON")
    rpb.add_argument("--out", type=Path, default=Path("reports/B1-report.md"))
```

In `main`, after the `run-b` dispatch:

```python
    if args.command == "report-b":
        return _run_report_b(args)
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/cli/test_report_b.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
uv run ruff format src/agent_eval_lab/cli.py src/agent_eval_lab/reports/b_report.py tests/cli/test_report_b.py
uv run ruff check src/agent_eval_lab/cli.py src/agent_eval_lab/reports/b_report.py tests/cli/test_report_b.py
git add src/agent_eval_lab/cli.py src/agent_eval_lab/reports/b_report.py tests/cli/test_report_b.py
git commit -m "feat(b1-spike): add report-b CLI (owner verdicts + trials -> B-1 report)"
```

**Verification point:** `uv run pytest tests/reports/test_b_report.py tests/cli/test_report_b.py -q` green; pass_at_1 headline, skill delta, INVALID masking, claude-on-its-own-axis all proven.

---

## Phase 11 — Integrity guard test + runbook (spec §11.11 / §7 / §8 / §12)

### Task 11a: Integrity-boundary guard test

**Files:**
- Create: `tests/runners/test_b_integrity_guard.py`

Two guards (spec §8): (1) the candidate prompt + workdir cannot reference the evaluator store path; (2) `bash_edge`'s allowlist rejects any non-`playwright-cli` binary AND the `file://` guard blocks store reads via the browser.

- [ ] **Step 1: Write the guard tests**

```python
def test_render_b_prompt_does_not_reference_the_evaluator_store() -> None:
    from agent_eval_lab.datasets.b_tasks import render_b_prompt

    rendered = render_b_prompt(
        "Build the B-1 report.",
        save_name="m__b-b1-noskill__0000",
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
    )
    # The prompt never names evaluator.toml, evaluator-only, or a golden id (§7 / TRAP 2).
    low = rendered.lower()
    assert "evaluator.toml" not in low
    assert "evaluator-only" not in low
    assert "golden" not in low


def test_bash_allowlist_rejects_non_playwright_binary() -> None:
    from agent_eval_lab.runners.bash_edge import ALLOWED_BINS, parse_argv

    assert "playwright-cli" in ALLOWED_BINS
    # parse_argv accepts the bare cat name (allowlist check is in the executor), but
    # the executor refuses it; assert the allowlist itself excludes shells/cat.
    assert "cat" not in ALLOWED_BINS
    assert "bash" not in ALLOWED_BINS
    assert "sh" not in ALLOWED_BINS
    # A bare `cat evaluator.toml` parses (bare name) but is not allowlisted.
    argv = parse_argv("cat evaluator.toml")
    assert argv == ["cat", "evaluator.toml"]
    assert argv[0] not in ALLOWED_BINS


def test_file_scheme_store_read_is_blocked() -> None:
    from agent_eval_lab.runners.bash_edge import parse_argv

    # The one chat-loop residual vector (§7) — file:// navigation to the store — is closed.
    assert parse_argv("playwright-cli open file:///abs/evaluator.toml") is None
```

- [ ] **Step 2: Run to verify it passes (no new impl — guards already exist from Tasks 4 + 5a)**

Run: `uv run pytest tests/runners/test_b_integrity_guard.py -q`
Expected: PASS (3 tests). If any fails, the corresponding guard (Task 4 file-scheme reject or Task 5a no-store-leak) regressed — fix the source, not the test.

- [ ] **Step 3: Commit**

```bash
uv run ruff format tests/runners/test_b_integrity_guard.py
uv run ruff check tests/runners/test_b_integrity_guard.py
git add tests/runners/test_b_integrity_guard.py
git commit -m "test(b1-spike): integrity-boundary guards (no store leak, allowlist, file:// block)"
```

### Task 11b: B-1 live-run runbook

**Files:**
- Modify: append a runbook section to a run-docs file under `docs/2026-06-13-agentic-v1-domains-runs/` (locate the existing run-doc; if none fits, create `docs/2026-06-13-agentic-v1-domains-runs/B1-LIVE-RUNBOOK.md`).

- [ ] **Step 1: Locate the run docs**

Run: `ls docs/2026-06-13-agentic-v1-domains-runs/`
Pick the EXECUTE/run doc to append to; otherwise create `B1-LIVE-RUNBOOK.md` there.

- [ ] **Step 2: Write the runbook (owner-facing live-run procedure)**

Write this content (it documents the owner-deferred live steps — the build itself does NOT run any of these):

```markdown
## B-1 Live Spike runbook (owner-performed; deferred per spec §9)

Preconditions (spec §12 — all owner, before the live run):
1. `[candidate] password` set in `evaluator.toml` (currently empty); `bxu` confirmed
   least-privilege (CANNOT read the goldens).
2. `[candidate] url` set (e.g. `…/MicroStrategyLibrary/app`) and `[candidate] folder` chosen.
3. **Store relocation (§7):** move the evaluator store + `evaluator.toml` OUT of the repo
   tree and update `[store] path` BEFORE any `--driver claude` arm runs (the claude -p path
   is NOT OS-confined — a naive `./evaluator.toml` read must fail).
4. MSTR Library reachable from the run host (internal labs host / VPN).
5. `playwright-cli install --skills` run once on the host.

Calibrate FIRST (decision 6): run ONE trial (one model, noskill) and confirm it does NOT
hit `max_rounds` far from Save before the full 24-run sweep:

    uv run agent-eval-lab run-b --provider dashscope --model qwen3.7-max \
      --evaluator-config /relocated/evaluator.toml --arm noskill --out reports/b1-spike \
      --driver chat

Inspect `reports/b1-spike/b1-verdict-sheet-*.md`: if the single trial's stop_reason is
`max_rounds (censored)` with the object NOT near Save, raise max_rounds (or fix the prompt)
before the sweep.

Full sweep (per model × both arms; chat models run SEQUENTIALLY — never two models on the one
bxu login, §7):

    uv run agent-eval-lab run-b --provider dashscope --model qwen3.7-max --arm both ...
    uv run agent-eval-lab run-b --provider deepseek  --arm both ...
    uv run agent-eval-lab run-b --provider minimax   --arm both ...
    uv run agent-eval-lab run-b --driver claude --provider <claude> --arm both ...   # store relocated first

Score (Phase 2, manual): open each saved object in MSTR, score it against the
definition-match checklist (R1..R5) in the verdict sheet, and write
`verdicts.json` = `{run_uid: "PASS" | "FAIL" | "INVALID"}`.

Report (Phase 3, pure):

    uv run agent-eval-lab report-b --trials reports/b1-spike/trials-b-*.jsonl \
      --verdicts verdicts.json --prices evaluator-only/pricing.json \
      --out reports/b1-spike/B1-report.md

OUT of scope (owner-deferred, spec §9): the live MstrReadbackClient / automated readback /
exact-grid compare; OS-level claude -p confinement; the paid sweep itself. B-1 is a one-task
contingency (point summary, never a bootstrap CI).
```

- [ ] **Step 3: Commit**

```bash
git add docs/2026-06-13-agentic-v1-domains-runs/
git commit -m "docs(b1-spike): B-1 live-run runbook (preconditions, calibrate-first, store relocation)"
```

**Verification point:** the runbook documents every §12 precondition + the calibrate-first protocol + store relocation + the OUT-of-scope deferrals.

---

## Final verification (after all phases)

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS — the entire suite green (every pre-existing test + all new B-1 tests). No live MSTR / live provider anywhere.

- [ ] **Step 2: Lint the whole change**

Run: `uv run ruff check . && uv run ruff format --check .`
Expected: clean.

- [ ] **Step 3: Smoke the new CLI surfaces are registered**

Run: `uv run agent-eval-lab run-b --help && uv run agent-eval-lab report-b --help`
Expected: both print their help (parser wired).

**Done when:** the full suite is green, both new commands are registered, and the runbook is in place. The spike ships code + tests + runbook; live execution stays owner-deferred (spec §9).

---

## Spec coverage self-check

| Spec §11 item | Task | Notes |
| --- | --- | --- |
| 11.1 `run_trials_k_valid` extraction | Task 1 | Behavior-preserving; parity test + full `multi_run` suite re-run |
| 11.2 `BTrial` record | Task 2 | Grade-less, frozen, round-trips; ADR-0021 |
| 11.3 `b_live.py` | Task 3 | Task-scoped run_uid; invalid-tag vs censoring; k-valid loop |
| 11.4 `file://` guard | Task 4 | `parse_argv` file:-scheme reject |
| 11.5 chat driver + `render_b_prompt` | Tasks 5a, 5b | browse loop, max_rounds=50, allowlist; no password in prompt |
| 11.6 `claude -p` driver | Task 6 | reuses claude_cli_candidate; num_turns + total_cost_usd |
| 11.7 config extension | Task 7 | `[candidate] folder`; store relocation is runbook (11b) |
| 11.8 `run-b` CLI | Task 9 | per-model arms, BTrial writes, void sidecar, verdict sheet, auth/quota fail-fast |
| 11.9 `b_scoring.py` | Task 8 | verdict sheet, checklist, censored-stop flag |
| 11.10 `report-b` + `b_report.py` | Tasks 10a, 10b | pass_at_1 headline + pass_pow_3 + efficiency + skill delta + claude axis |
| 11.11 integrity guard + runbook | Tasks 11a, 11b | no-store-leak/allowlist/file:// guards + live runbook |

**OUT of scope (built nothing — owner-deferred per §9):** live `MstrReadbackClient`, automated readback / exact-grid compare; the paid 24-run sweep; OS-level `claude -p` confinement. The store relocation is an operational runbook step, not code.
