from pathlib import Path

from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.verification import ToolCallMatchSpec

DATASET = Path("examples/datasets/tool_use.jsonl")


def test_dataset_has_about_twenty_tasks():
    tasks = load_tasks(DATASET)
    assert 18 <= len(tasks) <= 22


def test_every_task_roundtrips_and_uses_tool_call_match():
    tasks = load_tasks(DATASET)
    for task in tasks:
        assert isinstance(task.verification, ToolCallMatchSpec)
        # round-trip integrity
        from agent_eval_lab.tasks.codec import from_dict
        from agent_eval_lab.tasks.task import Task

        assert from_dict(Task, to_dict(task)) == task


def test_capabilities_and_ids_are_distinct():
    tasks = load_tasks(DATASET)
    ids = [t.id for t in tasks]
    assert len(ids) == len(set(ids))
    assert {t.capability for t in tasks} <= {"tool_selection", "argument_extraction"}


def test_both_match_modes_present():
    tasks = load_tasks(DATASET)
    modes = {t.verification.match for t in tasks}
    assert "exact_sequence" in modes
    assert "multiset" in modes
