from agent_eval_lab.metrics.baseline import aggregate
from agent_eval_lab.reports.baseline import render_report
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.turns import MessageTurn


def _rr(task_id, run_index, passed, reason=None):
    traj = Trajectory(turns=(MessageTurn(role="assistant", content="x"),),
                      usage={"total_tokens": 15}, cost_usd=0.001, latency_ms=10,
                      run_index=run_index, termination_reason="stop")
    grade = GradeResult(grader_id="g", passed=passed, score=1.0 if passed else 0.0,
                        failure_reason=reason)
    return RunResult(task_id=task_id, condition_id="c", run_index=run_index,
                     trajectory=traj, grade=grade)


def test_render_is_deterministic_and_contains_headline_numbers():
    runs = [_rr("t1", 0, True), _rr("t1", 1, True), _rr("t2", 0, False, reason="wrong_tool")]
    summary = aggregate(runs)
    out_a = render_report(summary)
    out_b = render_report(summary)
    assert out_a == out_b
    assert "Baseline Report" in out_a
    assert "tasks passing all k: 1" in out_a
    assert "total runs: 3" in out_a
    assert "wrong_tool: 1" in out_a
