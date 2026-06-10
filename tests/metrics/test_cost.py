from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _run(prompt_tokens: int, completion_tokens: int) -> RunResult:
    return RunResult(
        task_id="a",
        condition_id="c",
        run_index=0,
        trajectory=Trajectory(
            turns=(),
            usage=Usage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_s=0.0,
            ),
            run_index=0,
            stop_reason="completed",
        ),
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )


def test_cost_is_tokens_times_price_per_million() -> None:
    results = (_run(500_000, 100_000), _run(500_000, 100_000))
    price = TokenPrice(input_per_mtok=1.0, output_per_mtok=5.0)

    assert total_cost_usd(results, price=price) == 1.0 + 1.0
