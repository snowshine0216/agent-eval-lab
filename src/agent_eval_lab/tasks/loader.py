"""EDGE: read JSONL dataset files into Task records."""

import json
from pathlib import Path

from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tasks.schema import Task


def load_tasks(path: Path) -> tuple[Task, ...]:
    lines = path.read_text().splitlines()
    tasks = tuple(parse_task(json.loads(line)) for line in lines if line.strip())
    seen: set[str] = set()
    for task in tasks:
        if task.id in seen:
            raise ValueError(f"duplicate task id: {task.id!r}")
        seen.add(task.id)
    return tasks
