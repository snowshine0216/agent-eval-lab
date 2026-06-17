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
