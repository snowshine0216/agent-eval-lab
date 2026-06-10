"""pass@1 (trial accuracy) and pass^k (task-level reliability), spec §4.6.

A task passes pass^k iff ALL of its runs pass; the estimand is the
proportion of tasks that pass every run — not trial-level accuracy.
"""

from collections.abc import Sequence

from agent_eval_lab.records.grade import RunResult


def _require_results(results: Sequence[RunResult]) -> None:
    if not results:
        raise ValueError("no results to aggregate")


def pass_at_1(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(1 for run in results if run.grade.passed) / len(results)


def pass_pow_k(results: Sequence[RunResult]) -> float:
    _require_results(results)
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(run.grade.passed)
    reliable = sum(1 for passes in by_task.values() if all(passes))
    return reliable / len(by_task)


def failure_counts(results: Sequence[RunResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in results:
        if run.grade.passed:
            continue
        key = run.grade.failure_reason or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return counts


def token_totals(results: Sequence[RunResult]) -> tuple[int, int]:
    prompt = sum(run.trajectory.usage.prompt_tokens for run in results)
    completion = sum(run.trajectory.usage.completion_tokens for run in results)
    return prompt, completion


def mean_latency_s(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(run.trajectory.usage.latency_s for run in results) / len(results)
