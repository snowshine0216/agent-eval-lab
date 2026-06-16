from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.reports.defects import (
    DefectInputGroup,
    TaskDefectCandidate,
    task_defect_candidates,
)


def _run(task_id, cond, passed, idx=0):
    return RunResult(
        task_id=task_id,
        condition_id=cond,
        run_index=idx,
        trajectory=Trajectory(
            turns=(MessageTurn(role="assistant", content="x"),),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
            run_index=idx,
            stop_reason="completed_natural",
            rounds=1,
        ),
        grade=GradeResult(
            grader_id="g", passed=passed, score=1.0 if passed else 0.0, evidence={}
        ),
    )


def test_unanimous_fail_is_a_candidate():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", False),), blocked=False),
    )
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=2, n_runs=2),)


def test_one_condition_passing_is_not_a_candidate():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", True),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", False),), blocked=False),
    )
    assert task_defect_candidates(groups) == ()


def test_vacuous_condition_without_records_does_not_block():
    # B has no records for t1 -> contributes nothing; A fails t1 unanimously.
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t2", "B", True),), blocked=False),
    )
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=1, n_runs=1),)


def test_blocked_condition_is_excluded():
    groups = (
        DefectInputGroup(label="A", runs=(_run("t1", "A", False),), blocked=False),
        DefectInputGroup(label="B", runs=(_run("t1", "B", True),), blocked=True),
    )
    # B is blocked -> excluded; A fails t1 unanimously -> candidate.
    out = task_defect_candidates(groups)
    assert out == (TaskDefectCandidate(task_id="t1", n_conditions=1, n_runs=1),)
