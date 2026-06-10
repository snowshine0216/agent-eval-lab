import json

from agent_eval_lab.records.trajectory import ParseFailure
from agent_eval_lab.records.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.runners.parse import parse_assistant_payload


def test_plain_content_becomes_assistant_message() -> None:
    parsed = parse_assistant_payload({"role": "assistant", "content": "Done."})

    assert parsed == MessageTurn(role="assistant", content="Done.")


def test_tool_calls_are_parsed_with_arguments_decoded() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {
                    "name": "search_docs",
                    "arguments": json.dumps({"query": "refund policy"}),
                },
            }
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ToolCallTurn)
    assert parsed.tool_calls[0].call_id == "call_1"
    assert parsed.tool_calls[0].arguments == {"query": "refund policy"}


def test_invalid_arguments_json_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "search_docs", "arguments": '{"query": '},
            }
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "not valid JSON" in parsed.error


def test_non_object_arguments_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "search_docs", "arguments": "[1, 2]"},
            }
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "JSON object" in parsed.error


def test_missing_function_name_is_a_parse_failure() -> None:
    message = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {"id": "c1", "type": "function", "function": {"arguments": "{}"}}
        ],
    }

    parsed = parse_assistant_payload(message)

    assert isinstance(parsed, ParseFailure)
    assert "name" in parsed.error


def test_neither_content_nor_tool_calls_is_a_parse_failure() -> None:
    parsed = parse_assistant_payload({"role": "assistant", "content": None})

    assert isinstance(parsed, ParseFailure)
