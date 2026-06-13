from agent_eval_lab.experiments.comparisons import run_planned_comparisons
from agent_eval_lab.experiments.schema import (
    MultiplicityFamily,
    PlannedComparison,
)
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _run(task_id, cond, passed):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0, stop_reason="completed_natural",
    )
    return RunResult(task_id=task_id, condition_id=cond, run_index=0, trajectory=traj,
                     grade=GradeResult(grader_id="g", passed=passed,
                                       score=1.0 if passed else 0.0, evidence={}))


def _arm(cond, pass_by_task):
    return [_run(t, cond, p) for t, p in pass_by_task.items()]


def test_run_planned_comparisons_applies_holm_and_reports_ci():
    tasks_pass_a = {f"t{i}": False for i in range(6)}
    tasks_pass_b = {f"t{i}": True for i in range(6)}
    runs_by = {
        "a": {"D": _arm("a", tasks_pass_a)},
        "b": {"D": _arm("b", tasks_pass_b)},
    }
    comps = (
        PlannedComparison(name="a_vs_b", family_id="F1", domain="D",
                          condition_a="a", condition_b="b", metric_name="pass_pow_k"),
    )
    family = MultiplicityFamily(id="F1", description="d", correction="holm", alpha=0.05)
    out = run_planned_comparisons(
        comparisons=comps, families=(family,), runs_by_condition_domain=runs_by,
        seed=20260613, n_resamples=2000, alpha_default=0.05,
    )
    assert len(out) == 1
    row = out[0]
    assert row.comparison_name == "a_vs_b"
    assert row.delta_point == 1.0          # pass^k(b)-pass^k(a) = 1 - 0 = 1
    assert row.decision.rejected is True   # clear separation survives Holm at m=1
    assert row.ci_lower is not None        # paired bootstrap CI populated


def test_missing_arm_is_reported_not_crashed():
    # Partial coverage: condition b has no D runs -> the comparison is SKIPPED.
    runs_by = {"a": {"D": _arm("a", {"t0": True})}, "b": {}}
    comps = (
        PlannedComparison(name="a_vs_b", family_id="F1", domain="D",
                          condition_a="a", condition_b="b", metric_name="pass_pow_k"),
    )
    family = MultiplicityFamily(id="F1", description="d", correction="holm", alpha=0.05)
    out = run_planned_comparisons(
        comparisons=comps, families=(family,), runs_by_condition_domain=runs_by,
        seed=1, n_resamples=100, alpha_default=0.05,
    )
    assert len(out) == 1
    assert out[0].skipped is True
    assert out[0].decision is None
