from pathlib import Path

from agent_eval_lab.reports.baseline import main


def test_cli_renders_report_from_recorded_runs(capsys):
    code = main(["examples/datasets/recorded_runs.jsonl"])
    out = capsys.readouterr().out
    assert code == 0
    assert "# Baseline Report" in out
    assert "total runs: 4" in out


def test_cli_committed_file_exists():
    assert Path("examples/datasets/recorded_runs.jsonl").exists()
