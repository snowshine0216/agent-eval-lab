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
