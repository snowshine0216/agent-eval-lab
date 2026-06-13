import math

from agent_eval_lab.experiments.aggregate import efficiency_summary
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt


def _run(rounds, prompt, completion, wall, safety_cap=False):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage=Usage(prompt_tokens=prompt, completion_tokens=completion, latency_s=wall),
        run_index=0,
        stop_reason="safety_cap" if safety_cap else "completed_natural",
        rounds=rounds, wall_time_s=wall, safety_cap_bound=safety_cap,
    )
    return RunResult(
        task_id="t", condition_id="m1", run_index=0, trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}),
    )


def _outcome(runs):
    attempts = tuple(
        TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
    )
    return ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)


def test_efficiency_summary_medians_and_token_total():
    runs = [_run(3, 10, 5, 1.0), _run(5, 20, 10, 2.0), _run(7, 30, 15, 3.0)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    assert s.median_rounds == 5
    assert s.total_tokens == (10 + 20 + 30) + (5 + 10 + 15)
    assert math.isclose(s.median_wall_time_s, 2.0)
    assert s.n_censored == 0


def test_efficiency_summary_counts_safety_cap_as_censored():
    runs = [_run(3, 10, 5, 1.0), _run(200, 99, 99, 60.0, safety_cap=True)]
    s = efficiency_summary(outcomes=(_outcome(runs),))
    # the capped run is right-censored (D35), counted not hidden
    assert s.n_censored == 1
