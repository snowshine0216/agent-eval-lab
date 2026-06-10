"""Dataset conformance: every task loads, references known tools, and has
schema-valid expected calls (the dataset can never be wrong about the world).
"""

from pathlib import Path

from agent_eval_lab.tasks.loader import load_tasks
from agent_eval_lab.tasks.schema import ToolCallMatchSpec
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

_REPO = Path(__file__).parent.parent.parent
DATASET = _REPO / "examples/datasets/workspace_tool_use_v1.jsonl"


def test_dataset_has_twenty_tasks_across_three_capabilities() -> None:
    tasks = load_tasks(DATASET)

    assert len(tasks) == 20
    capabilities = {task.capability for task in tasks}
    assert capabilities == {"tool_selection", "argument_extraction", "multi_step"}


def test_every_task_references_known_tools_and_valid_expected_calls() -> None:
    for task in load_tasks(DATASET):
        for name in task.input.available_tools:
            assert name in WORKSPACE_TOOLS, f"{task.id}: unknown tool {name}"
        assert isinstance(task.verification, ToolCallMatchSpec)
        for call in task.verification.expected_tool_calls:
            tool = WORKSPACE_TOOLS[call.name]
            error = validate_args(tool.parameters, call.arguments)
            assert error is None, f"{task.id}: expected call invalid: {error}"


def test_every_task_has_initial_state_and_dev_split() -> None:
    for task in load_tasks(DATASET):
        assert task.initial_state is not None, task.id
        assert task.metadata.split == "dev"
        assert task.metadata.world_template_id == "workspace-v1"
