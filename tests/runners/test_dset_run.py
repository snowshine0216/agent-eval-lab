from pathlib import Path

import httpx

from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.dset_run import (
    make_snapshot_validity_fn,
    run_dset,
)
from agent_eval_lab.tasks.schema import FactKeySpec, Task, TaskInput, TaskMetadata


def _fake_config() -> ProviderConfig:
    return ProviderConfig(
        id="local",
        base_url="http://localhost:11434/v1",
        api_key_env="",
        model_id="test",
    )


def _make_q02_task(tmp_path: Path) -> Task:
    spec = FactKeySpec(
        required=("1.34",),
        forbidden=(),
        page_snapshot="Kubernetes 1.34",
        page_snapshot_sha256="match",
        level=1,
    )
    return Task(
        id="cmc-q02",
        capability="docs_qa",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="What k8s version?"),),
            available_tools=("bash",),
        ),
        verification=spec,
        metadata=TaskMetadata(
            split="held_out",
            version="cmc-dset-v1",
            provenance="test",
        ),
    )


def _run(stop_reason="completed_natural", sha="match"):
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="1.34"),),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason=stop_reason,
    )
    return RunResult(
        task_id="cmc-q02",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="fact_key",
            passed=True,
            score=1.0,
            evidence={"page_snapshot_sha256": sha},
            failure_reason=None,
        ),
    )


def test_snapshot_validity_fn_marks_hash_mismatch_invalid():
    # The validity_fn is satisfied iff the run's recorded page hash matches the
    # reference (D36): a mismatch -> invalid (env), excluded from pass^k.
    validity_fn = make_snapshot_validity_fn(reference_sha256="match")
    assert validity_fn(_run(sha="match")) is True
    assert validity_fn(_run(sha="DIFFERENT")) is False


def test_snapshot_validity_fn_treats_missing_hash_as_valid():
    # review L1: a run with NO recorded snapshot hash (model produced no answer /
    # failed before grading) is a MODEL failure, not env drift -> VALID, so it
    # counts as a failed trial and does not spuriously VOID the task.
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import Trajectory, Usage

    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed_natural",
    )
    run = RunResult(
        task_id="cmc-q02",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="fact_key",
            passed=False,
            score=0.0,
            evidence={},
            failure_reason="no assistant message",
        ),
    )
    validity_fn = make_snapshot_validity_fn(reference_sha256="match")
    assert validity_fn(run) is True


def test_run_dset_threads_k_valid_and_records(monkeypatch, tmp_path):
    # Stub run_task_k_valid so this is a pure-wiring test (no provider/network).
    from agent_eval_lab.runners import dset_run

    captured = {}

    def fake_k_valid(**kwargs):
        captured.update(kwargs)
        from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt

        r = _run()
        return ReplacementOutcome(
            valid_runs=(r,) * kwargs["k_valid"],
            attempts=(TrialAttempt(attempt_index=0, valid=True, run=r),),
            void=False,
        )

    monkeypatch.setattr(dset_run, "run_task_k_valid", fake_k_valid)

    outcomes = run_dset(
        evaluator_store=tmp_path,  # an empty store is fine: tasks are injected
        tasks=(_make_q02_task(tmp_path),),
        config=_fake_config(),
        http_client=httpx.Client(),
        k_valid=5,
        max_invalid_rate=0.40,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=lambda: None,  # tolerated by the stub
    )
    assert captured["k_valid"] == 5
    assert "executor" in captured  # a bash executor was threaded
    assert "validity_fn" in captured  # the snapshot-hash validity_fn was threaded
    assert len(outcomes) == 1
