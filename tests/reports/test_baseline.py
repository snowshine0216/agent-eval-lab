import pytest

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.reports.baseline import build_baseline_report, render_markdown


def _run(
    task_id: str,
    run_index: int,
    passed: bool,
    failure_reason: str | None = None,
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
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=passed,
            score=1.0 if passed else 0.0,
            evidence={},
            failure_reason=failure_reason,
        ),
    )


RESULTS = (
    _run("a", 0, True),
    _run("a", 1, True),
    _run("b", 0, False, "wrong_args"),
    _run("b", 1, False, "schema_violation"),
)


def test_build_report_aggregates_metrics() -> None:
    report = build_baseline_report(
        RESULTS, dataset_id="workspace_tool_use_v1", condition_id="local:qwen3-8b", k=2
    )

    assert report.n_tasks == 2
    assert report.k == 2
    assert report.pass_at_1 == 0.5
    assert report.pass_pow_k == 0.5
    assert report.failure_counts == {"wrong_args": 1, "schema_violation": 1}
    assert report.prompt_tokens == 400
    assert report.completion_tokens == 80
    assert report.total_cost_usd is None
    assert report.mean_latency_s == 0.5


def test_build_report_computes_cost_when_price_given() -> None:
    report = build_baseline_report(
        RESULTS,
        dataset_id="d",
        condition_id="c",
        k=2,
        price=TokenPrice(input_per_mtok=1.0, output_per_mtok=5.0),
    )

    assert report.total_cost_usd == (400 * 1.0 + 80 * 5.0) / 1_000_000


def test_render_markdown_contains_headline_numbers() -> None:
    report = build_baseline_report(
        RESULTS, dataset_id="workspace_tool_use_v1", condition_id="local:qwen3-8b", k=2
    )

    text = render_markdown(report)

    assert "# Baseline report — local:qwen3-8b" in text
    assert "pass@1 (trial accuracy): 0.500" in text
    assert "pass^2 (task reliability): 0.500" in text
    assert "| wrong_args | 1 |" in text
    assert "not computed" in text


def test_render_markdown_handles_no_failures() -> None:
    report = build_baseline_report(
        (_run("a", 0, True),), dataset_id="d", condition_id="c", k=1
    )

    assert "No failures recorded." in render_markdown(report)


def test_build_report_rejects_k_mismatching_data() -> None:
    with pytest.raises(ValueError, match="k=3 but data has 2"):
        build_baseline_report(RESULTS, dataset_id="d", condition_id="c", k=3)


def test_build_report_rejects_unequal_runs_per_task() -> None:
    lopsided = RESULTS + (_run("c", 0, True),)

    with pytest.raises(ValueError, match="unequal runs per task"):
        build_baseline_report(lopsided, dataset_id="d", condition_id="c", k=2)


def test_build_report_rejects_empty_results() -> None:
    with pytest.raises(ValueError, match="no results"):
        build_baseline_report((), dataset_id="d", condition_id="c", k=1)
