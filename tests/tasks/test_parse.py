import pytest

from agent_eval_lab.tasks.parse import parse_task, verification_from_dict
from agent_eval_lab.tasks.schema import OutputMatchSpec, ToolCallMatchSpec

TASK_DATA = {
    "id": "ws-001",
    "capability": "tool_selection",
    "input": {
        "messages": [
            {
                "type": "message",
                "role": "system",
                "content": "You are a support agent.",
            },
            {
                "type": "message",
                "role": "user",
                "content": "Search the docs for 'refund policy'.",
            },
        ],
        "available_tools": ["search_docs", "create_ticket", "update_ticket"],
    },
    "verification": {
        "type": "tool_call_match",
        "expected_tool_calls": [
            {"name": "search_docs", "arguments": {"query": "refund policy"}}
        ],
        "match": "exact_sequence",
    },
    "metadata": {
        "split": "dev",
        "version": "1",
        "provenance": "hand_written",
        "world_template_id": "workspace-v1",
    },
    "initial_state": {"docs": {}, "tickets": {}},
}


def test_parse_task_builds_full_record() -> None:
    task = parse_task(TASK_DATA)

    assert task.id == "ws-001"
    assert task.capability == "tool_selection"
    assert len(task.input.messages) == 2
    assert task.input.available_tools == (
        "search_docs",
        "create_ticket",
        "update_ticket",
    )
    assert isinstance(task.verification, ToolCallMatchSpec)
    assert task.verification.expected_tool_calls[0].name == "search_docs"
    assert task.metadata.split == "dev"
    assert task.metadata.world_template_id == "workspace-v1"
    assert task.metadata.difficulty_knob is None
    assert task.initial_state == {"docs": {}, "tickets": {}}


def test_parse_task_rejects_bad_split() -> None:
    bad = {**TASK_DATA, "metadata": {**TASK_DATA["metadata"], "split": "test"}}

    with pytest.raises(ValueError, match="split"):
        parse_task(bad)


def test_parse_task_rejects_non_message_input_turns() -> None:
    bad_input = {
        **TASK_DATA["input"],
        "messages": [
            {
                "type": "tool_result",
                "call_id": "c1",
                "outcome": {"type": "success", "result": None},
            }
        ],
    }

    with pytest.raises(ValueError, match="message"):
        parse_task({**TASK_DATA, "input": bad_input})


def test_verification_from_dict_parses_output_match() -> None:
    spec = verification_from_dict(
        {"type": "output_match", "expected_output": "Done.", "normalizer": None}
    )

    assert isinstance(spec, OutputMatchSpec)
    assert spec.expected_output == "Done."
    assert spec.normalizer is None


def test_verification_from_dict_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown verification type"):
        verification_from_dict({"type": "final_state", "constraints": []})
