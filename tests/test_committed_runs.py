"""Criterion 13: every committed live-run line parses through the existing
loader and classifies totally under fc-v2. Skips until live artifacts land."""

from pathlib import Path

import pytest

from agent_eval_lab.cli import _load_run_results
from agent_eval_lab.reports.classify import classify_run

RUNS_DIR = Path("docs/2026-06-11-coding-agent-eval/runs")


def _committed_runs_files() -> list:
    files = sorted(RUNS_DIR.glob("runs-*.jsonl"))
    if files:
        return files
    return [
        pytest.param(
            None, marks=pytest.mark.skip(reason="live artifacts not captured yet")
        )
    ]


@pytest.mark.parametrize("path", _committed_runs_files())
def test_committed_runs_parse_and_classify(path: Path) -> None:
    runs = _load_run_results(path)
    assert 0 < len(runs) <= 45  # 15 tasks x k=3 per condition
    assert len({run.condition_id for run in runs}) == 1  # homogeneous file
    for run in runs:
        classification = classify_run(run)  # total: never raises
        assert classification.classifier_version == "fc-v3"
