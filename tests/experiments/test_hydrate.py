"""Tests for experiments/hydrate.py — content-verified run hydration.

The hydration function reads JSONL artifact files, locates exactly one record
by run_uid, and verifies SHA256 over its canonical bytes.
"""

import hashlib
import json
from pathlib import Path

import pytest

from agent_eval_lab.experiments.hydrate import hydrate_run_record
from agent_eval_lab.experiments.schema import ExperimentRunRef
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import run_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _make_run(
    *,
    task_id: str = "t1",
    condition_id: str = "deepseek:deepseek-v4-pro",
    run_uid: str,
) -> RunResult:
    traj = Trajectory(
        schema_version="2",
        turns=(),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
        rounds=1,
        wall_time_s=0.1,
        tool_call_counts={},
        safety_cap_bound=False,
        env_health=None,
        run_uid=run_uid,
    )
    return RunResult(
        task_id=task_id,
        condition_id=condition_id,
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="g1", passed=True, score=1.0, evidence={}, failure_reason=None
        ),
    )


def _canonical_bytes(run: RunResult) -> bytes:
    """The canonical bytes used for SHA256: deterministic JSON of run_result_to_dict."""
    d = run_result_to_dict(run)
    return json.dumps(
        d, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode()


def _sha256_of(run: RunResult) -> str:
    return hashlib.sha256(_canonical_bytes(run)).hexdigest()


def _write_jsonl(path: Path, runs: list[RunResult]) -> None:
    lines = [json.dumps(run_result_to_dict(r)) for r in runs]
    path.write_text("\n".join(lines) + "\n")


# ---------- happy path ----------

def test_hydrate_run_record_returns_record(tmp_path: Path) -> None:
    run = _make_run(run_uid="uid-001")
    artifact = tmp_path / "runs.jsonl"
    _write_jsonl(artifact, [run])
    sha = _sha256_of(run)
    ref = ExperimentRunRef(
        run_uid="uid-001",
        artifact_sha256=sha,
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    record = hydrate_run_record(ref=ref, artifact_paths=[artifact])
    assert record.run.trajectory.run_uid == "uid-001"


def test_hydrate_run_record_correct_run_returned(tmp_path: Path) -> None:
    run_a = _make_run(task_id="t_a", run_uid="uid-A")
    run_b = _make_run(task_id="t_b", run_uid="uid-B")
    artifact = tmp_path / "runs.jsonl"
    _write_jsonl(artifact, [run_a, run_b])
    sha = _sha256_of(run_b)
    ref = ExperimentRunRef(
        run_uid="uid-B",
        artifact_sha256=sha,
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    record = hydrate_run_record(ref=ref, artifact_paths=[artifact])
    assert record.run.task_id == "t_b"


def test_hydrate_run_record_searches_multiple_files(tmp_path: Path) -> None:
    run_a = _make_run(task_id="t_a", run_uid="uid-A")
    run_b = _make_run(task_id="t_b", run_uid="uid-B")
    file_a = tmp_path / "a.jsonl"
    file_b = tmp_path / "b.jsonl"
    _write_jsonl(file_a, [run_a])
    _write_jsonl(file_b, [run_b])
    sha = _sha256_of(run_b)
    ref = ExperimentRunRef(
        run_uid="uid-B",
        artifact_sha256=sha,
        domain="D",
        repeat_index=0,
        attempt_index=0,
    )
    record = hydrate_run_record(ref=ref, artifact_paths=[file_a, file_b])
    assert record.run.task_id == "t_b"


# ---------- hard-fail: zero matches ----------

def test_hydrate_raises_when_run_uid_not_found(tmp_path: Path) -> None:
    run = _make_run(run_uid="uid-001")
    artifact = tmp_path / "runs.jsonl"
    _write_jsonl(artifact, [run])
    ref = ExperimentRunRef(
        run_uid="uid-MISSING",
        artifact_sha256="0" * 64,
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    with pytest.raises((ValueError, LookupError)):
        hydrate_run_record(ref=ref, artifact_paths=[artifact])


# ---------- hard-fail: >1 matches ----------

def test_hydrate_raises_when_run_uid_duplicated(tmp_path: Path) -> None:
    run_a = _make_run(task_id="t_a", run_uid="uid-DUP")
    run_b = _make_run(task_id="t_b", run_uid="uid-DUP")
    artifact = tmp_path / "runs.jsonl"
    _write_jsonl(artifact, [run_a, run_b])
    ref = ExperimentRunRef(
        run_uid="uid-DUP",
        artifact_sha256="0" * 64,
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    with pytest.raises((ValueError, LookupError)):
        hydrate_run_record(ref=ref, artifact_paths=[artifact])


# ---------- hard-fail: SHA mismatch ----------

def test_hydrate_raises_on_sha_mismatch(tmp_path: Path) -> None:
    run = _make_run(run_uid="uid-001")
    artifact = tmp_path / "runs.jsonl"
    _write_jsonl(artifact, [run])
    ref = ExperimentRunRef(
        run_uid="uid-001",
        artifact_sha256="deadbeef" * 8,  # wrong hash (64 chars)
        domain="F",
        repeat_index=0,
        attempt_index=0,
    )
    with pytest.raises((ValueError, AssertionError)):
        hydrate_run_record(ref=ref, artifact_paths=[artifact])
