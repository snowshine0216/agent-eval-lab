"""Pure baseline aggregation: pass-over-k, cost/latency, failure-category counts."""

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from agent_eval_lab.tasks.grading import RunResult


@dataclass(frozen=True, kw_only=True)
class TaskSummary:
    task_id: str
    runs: int
    passes: int
    pass_over_k: bool


@dataclass(frozen=True, kw_only=True)
class BaselineSummary:
    per_task: dict[str, TaskSummary]
    total_runs: int
    tasks_passing_all_k: int
    total_cost_usd: float
    mean_latency_ms: float
    failure_counts: dict[str, int]


def aggregate(runs: Sequence[RunResult]) -> BaselineSummary:
    """Aggregate RunResults into a deterministic baseline summary."""
    task_ids = list(dict.fromkeys(r.task_id for r in runs))
    by_task = {tid: [r for r in runs if r.task_id == tid] for tid in task_ids}
    per_task = {
        task_id: TaskSummary(
            task_id=task_id,
            runs=len(group),
            passes=sum(1 for r in group if r.grade.passed),
            pass_over_k=all(r.grade.passed for r in group),
        )
        for task_id, group in by_task.items()
    }
    failures = Counter(
        r.grade.failure_reason for r in runs if r.grade.failure_reason is not None
    )
    total_latency = sum(r.trajectory.latency_ms for r in runs)
    return BaselineSummary(
        per_task=per_task,
        total_runs=len(runs),
        tasks_passing_all_k=sum(1 for s in per_task.values() if s.pass_over_k),
        total_cost_usd=round(sum(r.trajectory.cost_usd for r in runs), 8),
        mean_latency_ms=(total_latency / len(runs)) if runs else 0.0,
        failure_counts=dict(failures),
    )
