from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.runners.hashing import trajectory_hash
from agent_eval_lab.runners.runner import RunLimits, run_task
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS, initial_state


def _task():
    return Task(
        id="t1", capability="tool_selection",
        input=TaskInput(messages=(MessageTurn(role="user", content="go"),),
                        available_tools=({"name": "search_docs"},)),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs", arguments={"query": "x"}),)),
        metadata=TaskMetadata(split="dev", version="1", provenance="handwritten",
                              world_template_id="workspace", difficulty_knob="baseline"),
        initial_state=initial_state(),
    )


def _model():
    return FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}},
        {"type": "message", "content": "done"},
    ]})


@given(st.just(0))
def test_same_inputs_same_trajectory_hash(_seed):
    a = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())[0]
    b = run_task(_task(), _model(), TOOL_SCHEMAS, k=1, limits=RunLimits())[0]
    assert trajectory_hash(a.trajectory) == trajectory_hash(b.trajectory)
