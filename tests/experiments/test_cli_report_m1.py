import json
from pathlib import Path

from agent_eval_lab.cli import main
from agent_eval_lab.experiments.m1_spec import build_m1_spec
from agent_eval_lab.experiments.spec_hash import freeze_spec
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import run_result_to_dict
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _runs_jsonl(path: Path, cond: str):
    rows = []
    for ti in range(3):
        for ri in range(5):
            r = RunResult(
                task_id=f"t{ti}", condition_id=cond, run_index=ri,
                trajectory=Trajectory(
                    turns=(MessageTurn(role="assistant", content="x"),),
                    usage=Usage(
                        prompt_tokens=10, completion_tokens=5, latency_s=0.1
                    ),
                    run_index=ri, stop_reason="completed_natural", rounds=3,
                ),
                grade=GradeResult(grader_id="g", passed=True, score=1.0, evidence={}))
            rows.append(json.dumps(run_result_to_dict(r)))
    path.write_text("\n".join(rows) + "\n")


def test_report_m1_writes_markdown(tmp_path):
    spec = freeze_spec(
        build_m1_spec(dataset_snapshot_hash="ds", pricing_snapshot_hash="pr")
    )
    spec_path = tmp_path / "spec.json"
    from agent_eval_lab.cli import _spec_to_dict
    spec_path.write_text(json.dumps(_spec_to_dict(spec)))
    cond = "deepseek:deepseek-v4-pro"
    runs = tmp_path / "runs-d.jsonl"
    _runs_jsonl(runs, cond)
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({
        "snapshot_date": "2026-06-13",
        "prices": {cond: {"input_per_mtok": 1.0, "output_per_mtok": 2.0}},
    }))
    out = tmp_path / "m1.md"
    rc = main([
        "report-m1", "--spec", str(spec_path),
        "--runs", f"D:{cond}={runs}",
        "--prices", str(prices), "--out", str(out),
        "--seed", "20260613", "--n-resamples", "200", "--alpha", "0.05",
    ])
    assert rc == 0
    md = out.read_text()
    assert spec.spec_hash in md
    assert "Per-domain scores" in md
    assert "not yet run" in md.lower()  # F and B absent in this D-only report
