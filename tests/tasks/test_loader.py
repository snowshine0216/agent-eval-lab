import json
from pathlib import Path

import pytest

from agent_eval_lab.tasks.loader import load_tasks

LINE = {
    "id": "ws-001",
    "capability": "tool_selection",
    "input": {
        "messages": [{"type": "message", "role": "user", "content": "hi"}],
        "available_tools": ["search_docs"],
    },
    "verification": {
        "type": "tool_call_match",
        "expected_tool_calls": [{"name": "search_docs", "arguments": {"query": "x"}}],
        "match": "exact_sequence",
    },
    "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
}


def _write(path: Path, lines: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(line) for line in lines) + "\n")
    return path


def test_load_tasks_reads_jsonl(tmp_path: Path) -> None:
    second = {**LINE, "id": "ws-002"}
    dataset = _write(tmp_path / "tasks.jsonl", [LINE, second])

    tasks = load_tasks(dataset)

    assert [t.id for t in tasks] == ["ws-001", "ws-002"]


def test_load_tasks_skips_blank_lines(tmp_path: Path) -> None:
    dataset = tmp_path / "tasks.jsonl"
    dataset.write_text(json.dumps(LINE) + "\n\n")

    assert len(load_tasks(dataset)) == 1


def test_load_tasks_rejects_duplicate_ids(tmp_path: Path) -> None:
    dataset = _write(tmp_path / "tasks.jsonl", [LINE, LINE])

    with pytest.raises(ValueError, match="duplicate task id"):
        load_tasks(dataset)
