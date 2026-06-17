"""EDGE: run a task k times (multi-run from day 1) and grade every run."""

from collections.abc import Callable, Mapping
from dataclasses import dataclass

import httpx

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import ApplyFn, Executor, run_single
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply


def effective_max_steps(task: Task, *, default: int) -> int:
    """ADR-0004: the per-task metadata.max_steps WINS when present; the CLI
    default is the fallback for tasks without one (a floor, never a cap).

    Retained as the per-task budget resolver for item-002 ExperimentSpec wiring;
    the censoring loop no longer turn-bounds on it (the safety cap governs)."""
    declared = task.metadata.max_steps
    return declared if declared is not None else default


def _grade_one(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    trajectory: Trajectory,
) -> GradeResult:
    verdicts = precompute_execution_verdicts(
        verification=task.verification, trajectory=trajectory
    )
    grade = grade_trajectory(
        verification=task.verification,
        trajectory=trajectory,
        registry=registry,
        initial_state=task.initial_state,
        verdicts=verdicts,
    )
    return grade


def _run_one(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    condition: str,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn,
    executor: Executor | None,
    health_probe_fn: "Callable[[], EnvHealth] | None",
    safety_cap: int = 200,
    max_rounds: int | None = None,
) -> RunResult:
    trajectory = run_single(
        task=task,
        registry=registry,
        config=config,
        http_client=http_client,
        run_index=run_index,
        temperature=temperature,
        max_tokens=max_tokens,
        apply_fn=apply_fn,
        executor=executor,
        run_uid=f"{condition}__{run_index:04d}",
        health_probe_fn=health_probe_fn,
        safety_cap=safety_cap,
        max_rounds=max_rounds,
    )
    grade = _grade_one(task=task, registry=registry, trajectory=trajectory)
    return RunResult(
        task_id=task.id,
        condition_id=condition,
        run_index=run_index,
        trajectory=trajectory,
        grade=grade,
    )


def run_task_k(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k: int,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
) -> tuple[RunResult, ...]:
    """Backward-compatible multi-run: k runs, every run valid, no replacement.
    `max_steps` is accepted for CLI compatibility but no longer bounds the loop
    (the censoring contract's safety cap governs)."""
    condition = condition_id(config)
    return tuple(
        _run_one(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            condition=condition,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=apply_fn,
            executor=executor,
            health_probe_fn=None,
        )
        for run_index in range(k)
    )


@dataclass(frozen=True, kw_only=True)
class TrialAttempt:
    attempt_index: int
    valid: bool
    run: RunResult


@dataclass(frozen=True, kw_only=True)
class ReplacementOutcome:
    valid_runs: tuple[RunResult, ...]
    attempts: tuple[TrialAttempt, ...]
    void: bool  # True iff the max-invalid-rate threshold tripped before k valid


def _is_invalid(
    run: RunResult, validity_fn: "Callable[[RunResult], bool] | None"
) -> bool:
    """D34/D21: a trial is invalid iff its env was unhealthy OR validity_fn says so."""
    if run.trajectory.stop_reason == "env_unhealthy":
        return True
    if validity_fn is not None and validity_fn(run) is False:
        return True
    return False


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
