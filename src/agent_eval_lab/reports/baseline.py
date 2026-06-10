"""Pure baseline report renderer. File write + CLI live at the edge (Task 21)."""

from agent_eval_lab.metrics.baseline import BaselineSummary


def render_report(summary: BaselineSummary) -> str:
    """Render a deterministic plain-text baseline report from a summary (pure)."""
    lines = ["# Baseline Report", ""]
    lines.append(f"total runs: {summary.total_runs}")
    lines.append(f"tasks: {len(summary.per_task)}")
    lines.append(f"tasks passing all k: {summary.tasks_passing_all_k}")
    lines.append(f"total cost (USD): {summary.total_cost_usd}")
    lines.append(f"mean latency (ms): {summary.mean_latency_ms}")
    lines.append("")
    lines.append("## Per-task (passes/runs, pass^k)")
    for task_id in sorted(summary.per_task):
        s = summary.per_task[task_id]
        lines.append(f"- {task_id}: {s.passes}/{s.runs} pass^k={s.pass_over_k}")
    lines.append("")
    lines.append("## Failure categories")
    if summary.failure_counts:
        for category in sorted(summary.failure_counts):
            lines.append(f"- {category}: {summary.failure_counts[category]}")
    else:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI edge: render a baseline report from a RunResult JSONL file."""
    import sys
    from pathlib import Path

    from agent_eval_lab.metrics.baseline import aggregate
    from agent_eval_lab.tasks.loader import load_run_results

    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        print("usage: python -m agent_eval_lab.reports.baseline <runs.jsonl>")
        return 2
    runs = load_run_results(Path(args[0]))
    print(render_report(aggregate(runs)), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
