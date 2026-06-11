"""World resolver: dataset tools -> world binding (item 004 criterion 1)."""

from pathlib import Path

import pytest

from agent_eval_lab.runners.pytest_edge import execute_request
from agent_eval_lab.runners.worlds import WorldBinding, resolve_world
from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS
from agent_eval_lab.tools.workspace import apply as workspace_apply


def test_pure_workspace_set_resolves_to_workspace_binding() -> None:
    binding = resolve_world(("search_docs", "create_ticket", "update_ticket"))
    assert binding == WorldBinding(
        registry=WORKSPACE_TOOLS, apply_fn=workspace_apply, executor=None
    )


def test_pure_code_set_resolves_to_code_binding_with_pytest_executor() -> None:
    binding = resolve_world(("read_file", "write_file", "list_files", "run_tests"))
    assert binding == WorldBinding(
        registry=CODE_WORLD_TOOLS, apply_fn=code_world_apply, executor=execute_request
    )


def test_partial_code_set_still_resolves_to_code_binding() -> None:
    assert resolve_world(("read_file",)).registry is CODE_WORLD_TOOLS


def test_cross_world_mix_raises_value_error_naming_offenders() -> None:
    with pytest.raises(ValueError, match="search_docs.*read_file|read_file"):
        resolve_world(("search_docs", "read_file"))


def test_unknown_name_raises_value_error_naming_it() -> None:
    with pytest.raises(ValueError, match="frobnicate"):
        resolve_world(("read_file", "frobnicate"))


def test_empty_tool_list_raises_value_error() -> None:
    with pytest.raises(ValueError, match="empty tool list"):
        resolve_world(())


def test_registries_are_disjoint_load_bearing_invariant() -> None:
    """Membership resolution is only sound while the name spaces stay disjoint:
    a future tool name reused across worlds must fail CI here (grill Q4)."""
    assert set(WORKSPACE_TOOLS) & set(CODE_WORLD_TOOLS) == set()


@pytest.mark.parametrize(
    ("dataset", "registry"),
    [
        ("examples/datasets/workspace_tool_use_v1.jsonl", WORKSPACE_TOOLS),
        ("examples/datasets/workspace_tool_use_v2.jsonl", WORKSPACE_TOOLS),
        ("examples/datasets/code_repair_v1.jsonl", CODE_WORLD_TOOLS),
    ],
)
def test_every_shipped_task_resolves_to_exactly_one_world(dataset, registry) -> None:
    for task in load_tasks(Path(dataset)):
        assert resolve_world(task.input.available_tools).registry is registry
