import json

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


def test_tooldef_renders_openai_function_format() -> None:
    rendered = tooldef_to_openai(WORKSPACE_TOOLS["search_docs"])

    assert rendered["type"] == "function"
    assert rendered["function"]["name"] == "search_docs"
    assert rendered["function"]["parameters"]["required"] == ["query"]


def test_message_turn_renders_role_and_content() -> None:
    assert turn_to_message(MessageTurn(role="user", content="hi")) == {
        "role": "user",
        "content": "hi",
    }


def test_tool_call_turn_renders_arguments_as_json_string() -> None:
    turn = ToolCallTurn(
        tool_calls=(
            ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
        )
    )

    rendered = turn_to_message(turn)

    assert rendered["role"] == "assistant"
    call = rendered["tool_calls"][0]
    assert call["id"] == "c1"
    assert json.loads(call["function"]["arguments"]) == {"query": "x"}


def test_tool_result_turns_render_success_and_failure() -> None:
    success = turn_to_message(
        ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"doc_ids": []}))
    )
    failure = turn_to_message(
        ToolResultTurn(call_id="c2", outcome=ToolFailure(error="schema violation: x"))
    )

    assert success == {
        "role": "tool",
        "tool_call_id": "c1",
        "content": json.dumps({"doc_ids": []}),
    }
    assert failure == {
        "role": "tool",
        "tool_call_id": "c2",
        "content": json.dumps({"error": "schema violation: x"}),
    }
