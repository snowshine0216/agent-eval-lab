"""Resume support for run-dset: a transient failure (network blip) mid-corpus must
not lose banked tasks — a relaunch skips completed tasks and appends the rest."""

from pathlib import Path

from agent_eval_lab.cli import _completed_dset_task_ids


def test_missing_files_means_nothing_done(tmp_path: Path) -> None:
    p = tmp_path / "runs-dset-x.jsonl"
    vp = tmp_path / "runs-dset-x.void.json"
    assert _completed_dset_task_ids(p, vp) == (set(), [])


def test_jsonl_task_ids_are_done(tmp_path: Path) -> None:
    p = tmp_path / "r.jsonl"
    vp = tmp_path / "r.void.json"
    p.write_text(
        '{"task_id": "cmc-q01", "run_index": 0}\n'
        '{"task_id": "cmc-q01", "run_index": 1}\n'
        '{"task_id": "cmc-q02", "run_index": 0}\n',
        encoding="utf-8",
    )
    done, voids = _completed_dset_task_ids(p, vp)
    assert done == {"cmc-q01", "cmc-q02"}
    assert voids == []


def test_void_sidecar_tasks_count_as_done(tmp_path: Path) -> None:
    p = tmp_path / "r.jsonl"
    vp = tmp_path / "r.void.json"
    p.write_text('{"task_id": "cmc-q01", "run_index": 0}\n', encoding="utf-8")
    vp.write_text('{"void_task_ids": ["cmc-q03"]}', encoding="utf-8")
    done, voids = _completed_dset_task_ids(p, vp)
    assert done == {"cmc-q01", "cmc-q03"}
    assert voids == ["cmc-q03"]


def test_malformed_lines_are_skipped_not_fatal(tmp_path: Path) -> None:
    p = tmp_path / "r.jsonl"
    p.write_text(
        '{"task_id": "cmc-q01", "run_index": 0}\nGARBAGE\n{"no_task": 1}\n',
        encoding="utf-8",
    )
    done, voids = _completed_dset_task_ids(p, tmp_path / "missing.void.json")
    assert done == {"cmc-q01"}
    assert voids == []


# ── run-dset env-invalid masking (provider 403/429/empty must be REPLACED, never
#    banked as valid — the gap that voided deepseek+glm on the first D roster) ──


def _run(*, stop_reason, error=None, snapshot=None):
    from agent_eval_lab.records.grade import GradeResult, RunResult
    from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage

    pf = ParseFailure(raw="x", error=error) if error is not None else None
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason=stop_reason,
        parse_failure=pf,
    )
    ev = {} if snapshot is None else {"page_snapshot_sha256": snapshot}
    return RunResult(
        task_id="cmc-q01",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(
            grader_id="fact_key",
            passed=False,
            score=0.0,
            evidence=ev,
            failure_reason=None,
        ),
    )


def test_dset_validity_masks_provider_error_even_without_reference() -> None:
    from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR, PROVIDER_ERROR
    from agent_eval_lab.runners.dset_run import make_dset_validity_fn

    v = make_dset_validity_fn(reference_sha256=None)
    # provider 403/429 and empty-choices -> invalid (replace), regardless of snapshot
    assert v(_run(stop_reason="parse_failure", error=PROVIDER_ERROR)) is False
    assert v(_run(stop_reason="parse_failure", error=NO_CHOICES_ERROR)) is False
    # a clean run with no reference -> valid
    assert v(_run(stop_reason="completed_natural")) is True


def test_dset_validity_combines_provider_mask_and_snapshot() -> None:
    from agent_eval_lab.records.trajectory import PROVIDER_ERROR
    from agent_eval_lab.runners.dset_run import make_dset_validity_fn

    ref = "a" * 64
    v = make_dset_validity_fn(reference_sha256=ref)
    assert v(_run(stop_reason="completed_natural", snapshot=ref)) is True  # match
    assert v(_run(stop_reason="completed_natural", snapshot="b" * 64)) is False  # drift
    assert v(_run(stop_reason="completed_natural")) is True  # no snapshot recorded
    # provider error is invalid even if (hypothetically) snapshot matched
    assert (
        v(_run(stop_reason="parse_failure", error=PROVIDER_ERROR, snapshot=ref))
        is False
    )
