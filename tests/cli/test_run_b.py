import argparse
import json
from pathlib import Path

from agent_eval_lab.records.trajectory import Trajectory, Usage


def _ok(run_index):
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=100, completion_tokens=50, latency_s=1.0),
        run_index=run_index,
        stop_reason="completed_natural",
        rounds=5,
        wall_time_s=8.0,
    )


def _write_cfg(tmp_path: Path) -> Path:
    toml = tmp_path / "evaluator.toml"
    toml.write_text(
        """
[store]
path = "{store}"
[health_probe]
url = "https://lab/auth"
username = "eval"
password = "x"
[skill]
strategy_test_path = "{skill}"
[candidate]
url = "https://lab/app"
username = "bxu"
password = "secret"
folder = "/Candidate/bxu"
[runner]
safety_cap = 200
k_valid = 3
max_invalid_rate = 0.4
[oracle.b_set]
readback = "playwright-cli"
project_id = "P1"
[oracle.b_set.goldens]
"b-b1" = "obj1"
""".format(store=tmp_path / "store", skill=tmp_path / "skill.md"),
        encoding="utf-8",
    )
    (tmp_path / "skill.md").write_text("# stripped skill\n", encoding="utf-8")
    return toml


def test_run_b_writes_trials_and_verdict_sheet_both_arms(tmp_path, monkeypatch) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    # The candidate factory returns a fake run_fn (no provider, no MSTR).
    def fake_factory(*, arm, condition_id, folder, login):
        def run_fn(task, run_index, save_name):
            return _ok(run_index)

        return run_fn

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="both",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0

    # One trials artifact per arm (task_id), BTrial JSONL (no "grade" key).
    noskill = list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    skill = list(out.glob("trials-b-*-b-b1-skill.jsonl"))
    assert len(noskill) == 1 and len(skill) == 1
    line = json.loads(noskill[0].read_text().splitlines()[0])
    assert "grade" not in line
    assert line["save_name"].endswith("__b-b1-noskill__0000")
    # A void sidecar + the verdict sheet (md + csv) exist.
    assert (noskill[0].with_suffix(".void.json")).exists()
    assert list(out.glob("b1-verdict-sheet-*.md"))
    assert list(out.glob("b1-verdict-sheet-*.csv"))


def test_run_b_single_arm(tmp_path) -> None:
    from agent_eval_lab import cli

    cfg = _write_cfg(tmp_path)
    out = tmp_path / "out"

    def fake_factory(*, arm, condition_id, folder, login):
        return lambda task, run_index, save_name: _ok(run_index)

    args = argparse.Namespace(
        provider="dashscope",
        model="qwen3.7-max",
        evaluator_config=cfg,
        out=out,
        arm="noskill",
        temperature=0.0,
        max_tokens=4096,
        driver="chat",
    )
    rc = cli._run_b_command(args, candidate_run_fn_factory=fake_factory)
    assert rc == 0
    assert list(out.glob("trials-b-*-b-b1-noskill.jsonl"))
    assert not list(out.glob("trials-b-*-b-b1-skill.jsonl"))
