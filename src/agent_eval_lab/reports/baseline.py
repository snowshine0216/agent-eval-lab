"""Baseline report: pure build + markdown rendering. File I/O stays in cli."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.metrics.reliability import (
    failure_counts,
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    token_totals,
)
from agent_eval_lab.records.grade import RunResult


@dataclass(frozen=True, kw_only=True)
class BaselineReport:
    dataset_id: str
    condition_id: str
    n_tasks: int
    k: int
    pass_at_1: float
    pass_pow_k: float
    failure_counts: Mapping[str, int]
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float | None
    mean_latency_s: float


def _validate_k(results: Sequence[RunResult], k: int) -> None:
    runs_per_task: dict[str, int] = {}
    for run in results:
        runs_per_task[run.task_id] = runs_per_task.get(run.task_id, 0) + 1
    counts = set(runs_per_task.values())
    if len(counts) > 1:
        raise ValueError(f"unequal runs per task: {sorted(counts)}")
    actual_k = counts.pop()
    if k != actual_k:
        raise ValueError(f"k={k} but data has {actual_k} runs per task")


def build_baseline_report(
    results: Sequence[RunResult],
    *,
    dataset_id: str,
    condition_id: str,
    k: int,
    price: TokenPrice | None = None,
) -> BaselineReport:
    _validate_k(results, k)
    prompt_tokens, completion_tokens = token_totals(results)
    return BaselineReport(
        dataset_id=dataset_id,
        condition_id=condition_id,
        n_tasks=len({run.task_id for run in results}),
        k=k,
        pass_at_1=pass_at_1(results),
        pass_pow_k=pass_pow_k(results),
        failure_counts=failure_counts(results),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_cost_usd=None if price is None else total_cost_usd(results, price=price),
        mean_latency_s=mean_latency_s(results),
    )


def render_markdown(report: BaselineReport) -> str:
    cost = (
        f"${report.total_cost_usd:.4f}"
        if report.total_cost_usd is not None
        else "not computed (no price given)"
    )
    lines = [
        f"# Baseline report — {report.condition_id}",
        "",
        f"- Dataset: `{report.dataset_id}`",
        f"- Tasks: {report.n_tasks} · runs per task: k={report.k}",
        f"- pass@1 (trial accuracy): {report.pass_at_1:.3f}",
        f"- pass^{report.k} (task reliability): {report.pass_pow_k:.3f}",
        f"- Tokens: {report.prompt_tokens} prompt"
        f" · {report.completion_tokens} completion",
        f"- Estimated cost: {cost}",
        f"- Mean run latency: {report.mean_latency_s:.2f}s",
        "",
        "## Failures by category",
        "",
    ]
    if not report.failure_counts:
        lines.append("No failures recorded.")
    else:
        lines.extend(["| category | count |", "| --- | --- |"])
        ordered = sorted(report.failure_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        lines.extend(f"| {name} | {count} |" for name, count in ordered)
    return "\n".join(lines) + "\n"
