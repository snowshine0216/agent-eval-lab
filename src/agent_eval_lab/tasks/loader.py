"""JSONL I/O edge for Task and RunResult. The only file access in tasks/."""

import json
from collections.abc import Iterable
from pathlib import Path

from agent_eval_lab.tasks.codec import from_dict, to_dict
from agent_eval_lab.tasks.grading import RunResult
from agent_eval_lab.tasks.task import Task


def _read_lines(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def load_tasks(path: Path) -> list[Task]:
    return [from_dict(Task, d) for d in _read_lines(path)]


def load_run_results(path: Path) -> list[RunResult]:
    return [from_dict(RunResult, d) for d in _read_lines(path)]


def write_run_results(path: Path, results: Iterable[RunResult]) -> None:
    lines = [json.dumps(to_dict(r)) for r in results]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")
