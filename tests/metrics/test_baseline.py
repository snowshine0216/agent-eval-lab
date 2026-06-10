from agent_eval_lab.metrics.baseline import aggregate
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.turns import MessageTurn


def _rr(task_id, run_index, passed, reason=None, cost=0.001, latency=10):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage={"total_tokens": 15},
        cost_usd=cost,
        latency_ms=latency,
        run_index=run_index,
        termination_reason="stop",
    )
    grade = GradeResult(
        grader_id="g",
        passed=passed,
        score=1.0 if passed else 0.0,
        failure_reason=reason,
    )
    return RunResult(
        task_id=task_id,
        condition_id="c",
        run_index=run_index,
        trajectory=traj,
        grade=grade,
    )


def test_pass_over_k_requires_all_runs_pass():
    runs = [_rr("t1", 0, True), _rr("t1", 1, False, reason="wrong_args")]
    summary = aggregate(runs)
    assert summary.per_task["t1"].runs == 2
    assert summary.per_task["t1"].passes == 1
    assert summary.per_task["t1"].pass_over_k is False


def test_aggregate_totals_and_failure_counts():
    runs = [
        _rr("t1", 0, True),
        _rr("t2", 0, False, reason="wrong_tool"),
        _rr("t2", 1, False, reason="schema_violation"),
    ]
    summary = aggregate(runs)
    assert summary.total_runs == 3
    assert summary.tasks_passing_all_k == 1  # only t1
    assert summary.failure_counts["wrong_tool"] == 1
    assert summary.failure_counts["schema_violation"] == 1
    assert round(summary.total_cost_usd, 6) == 0.003
    assert summary.mean_latency_ms == 10.0
