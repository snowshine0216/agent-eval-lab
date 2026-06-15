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
