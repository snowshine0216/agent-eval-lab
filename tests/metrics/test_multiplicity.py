import math

from agent_eval_lab.metrics.multiplicity import (
    PValue,
    bootstrap_diff_p_value,
    holm_step_down,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(task_id: str, condition_id: str, passed: bool) -> RunResult:
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="completed_natural",
    )
    return RunResult(
        task_id=task_id,
        condition_id=condition_id,
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def test_holm_step_down_orders_and_stops_at_first_non_reject():
    # Three p-values at alpha=0.05, m=3 -> thresholds 0.0167, 0.025, 0.05.
    ps = (
        PValue(name="c1", p=0.001),
        PValue(name="c2", p=0.04),
        PValue(name="c3", p=0.20),
    )
    decisions = holm_step_down(ps, alpha=0.05)
    by_name = {d.name: d for d in decisions}
    assert by_name["c1"].rejected is True   # 0.001 <= 0.0167
    assert by_name["c2"].rejected is False  # 0.04 > 0.025 -> stop
    assert by_name["c3"].rejected is False  # step-down: retained after c2 fails
    # Adjusted p is monotone non-decreasing in the sorted order.
    assert (
        by_name["c1"].adjusted_p <= by_name["c2"].adjusted_p <= by_name["c3"].adjusted_p
    )


def test_holm_adjusted_p_is_min_one_times_rank():
    ps = (PValue(name="a", p=0.02), PValue(name="b", p=0.03))
    decisions = {d.name: d for d in holm_step_down(ps, alpha=0.05)}
    # m=2: a is smallest -> 2*0.02=0.04; b -> max(0.04, 1*0.03)=0.04 (enforced monotone)
    assert math.isclose(decisions["a"].adjusted_p, 0.04, abs_tol=1e-9)
    assert math.isclose(decisions["b"].adjusted_p, 0.04, abs_tol=1e-9)


def test_bootstrap_diff_p_consistent_with_clear_separation():
    # a fails all 4 tasks, b passes all 4 -> Δ=+1.0, p should be small.
    tasks = ["t1", "t2", "t3", "t4"]
    a = [_run(t, "a", passed=False) for t in tasks]
    b = [_run(t, "b", passed=True) for t in tasks]
    p = bootstrap_diff_p_value(a, b, n_resamples=2000, seed=20260613)
    assert p < 0.05


def test_bootstrap_diff_p_no_effect_is_large():
    tasks = ["t1", "t2", "t3", "t4"]
    a = [_run(t, "a", passed=True) for t in tasks]
    b = [_run(t, "b", passed=True) for t in tasks]
    p = bootstrap_diff_p_value(a, b, n_resamples=2000, seed=20260613)
    assert math.isclose(p, 1.0, abs_tol=1e-9)


def test_bootstrap_diff_p_is_deterministic():
    tasks = ["t1", "t2", "t3"]
    a = [_run(t, "a", passed=(i == 0)) for i, t in enumerate(tasks)]
    b = [_run(t, "b", passed=True) for t in tasks]
    p1 = bootstrap_diff_p_value(a, b, n_resamples=500, seed=7)
    p2 = bootstrap_diff_p_value(a, b, n_resamples=500, seed=7)
    assert p1 == p2
