from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn


def test_scripted_steps_replayed_in_order():
    model = FakeModel(scripts={"t1": [
        {"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}},
        {"type": "message", "content": "done"},
    ]})
    first = model.respond(task_id="t1", step=0)
    second = model.respond(task_id="t1", step=1)
    assert isinstance(first, ToolCallTurn)
    assert first.tool_calls[0].name == "search_docs"
    assert isinstance(second, MessageTurn)


def test_deterministic_same_inputs_same_call_id():
    script = {"t1": [{"type": "tool_call", "name": "search_docs", "arguments": {"query": "x"}}]}
    a = FakeModel(scripts=script).respond(task_id="t1", step=0)
    b = FakeModel(scripts=script).respond(task_id="t1", step=0)
    assert a.tool_calls[0].call_id == b.tool_calls[0].call_id


def test_usage_is_fixed_per_step():
    model = FakeModel(scripts={"t1": [{"type": "message", "content": "hi"}]})
    _, usage = model.respond_with_usage(task_id="t1", step=0)
    assert usage == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
