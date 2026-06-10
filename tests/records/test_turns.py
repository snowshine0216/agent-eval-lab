from dataclasses import FrozenInstanceError

import pytest

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)


def test_message_turn_has_discriminator_and_is_frozen() -> None:
    turn = MessageTurn(role="user", content="hi")

    assert turn.type == "message"
    with pytest.raises(FrozenInstanceError):
        turn.content = "changed"  # type: ignore[misc]


def test_tool_call_turn_supports_parallel_calls() -> None:
    calls = (
        ToolCall(call_id="c1", name="search_docs", arguments={"query": "a"}),
        ToolCall(call_id="c2", name="search_docs", arguments={"query": "b"}),
    )
    turn = ToolCallTurn(tool_calls=calls)

    assert turn.type == "tool_call"
    assert turn.content is None
    assert len(turn.tool_calls) == 2


def test_tool_outcome_variants_are_mutually_exclusive_by_construction() -> None:
    success = ToolSuccess(result={"doc_ids": ["doc-1"]})
    failure = ToolFailure(error="schema violation: priority")

    assert success.type == "success"
    assert failure.type == "failure"
    assert not hasattr(success, "error")
    assert not hasattr(failure, "result")


def test_tool_result_turn_links_to_call_id() -> None:
    turn = ToolResultTurn(call_id="c1", outcome=ToolSuccess(result=None))

    assert turn.type == "tool_result"
    assert turn.call_id == "c1"
