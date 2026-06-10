import json
from pathlib import Path

from agent_eval_lab.runners.provider import (
    ProviderClient,
    ProviderConfig,
    _parse_arguments,
    build_request,
    parse_response,
)
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

CFG = ProviderConfig(
    id="fake",
    base_url="https://example.invalid/v1",
    api_key_env="FAKE_API_KEY",
    model_id="fake-model",
)


def test_build_request_uses_model_id_and_tools():
    req = build_request(
        CFG, messages=[{"role": "user", "content": "hi"}], tools=[{"name": "t"}]
    )
    assert req["model"] == "fake-model"
    assert req["messages"] == [{"role": "user", "content": "hi"}]
    assert req["tools"] == [{"name": "t"}]


def test_parse_response_message():
    payload = {
        "choices": [{"message": {"role": "assistant", "content": "hello"}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 1, "total_tokens": 4},
    }
    turn, usage = parse_response(CFG, payload)
    assert isinstance(turn, MessageTurn)
    assert turn.content == "hello"
    assert usage["total_tokens"] == 4


def test_parse_response_tool_calls_canonical():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {
                                "name": "create_ticket",
                                "arguments": '{"title": "x", "priority": "low"}',
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"total_tokens": 9},
    }
    turn, _ = parse_response(CFG, payload)
    assert isinstance(turn, ToolCallTurn)
    call = turn.tool_calls[0]
    assert call.call_id == "call_1"
    assert call.name == "create_ticket"
    assert call.arguments == {"title": "x", "priority": "low"}


def test_parse_arguments_json_object_string():
    assert _parse_arguments('{"a": 1}') == ({"a": 1}, None)


def test_parse_arguments_already_a_mapping():
    assert _parse_arguments({"a": 1}) == ({"a": 1}, None)


def test_parse_arguments_unparseable_returns_raw_error():
    assert _parse_arguments("{not json") == ({}, "{not json")


def test_parse_arguments_valid_json_but_not_an_object_is_an_error():
    # A JSON array/scalar is not a valid arguments object -> parse error, not coercion.
    assert _parse_arguments("[1, 2]") == ({}, "[1, 2]")


def test_malformed_arguments_recorded_as_parse_error_not_raw_sentinel():
    payload = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {"id": "c", "function": {"name": "t", "arguments": "{not json"}}
                    ]
                }
            }
        ],
        "usage": {"total_tokens": 1},
    }
    turn, _ = parse_response(CFG, payload)
    call = turn.tool_calls[0]
    assert call.arguments == {}
    assert call.arguments_parse_error == "{not json"


def test_client_reads_key_from_named_env(monkeypatch):
    monkeypatch.setenv("FAKE_API_KEY", "secret-123")
    captured = {}

    def transport(request):
        captured.update(request)
        return {
            "choices": [{"message": {"role": "assistant", "content": "ok"}}],
            "usage": {"total_tokens": 2},
        }

    client = ProviderClient(CFG, transport=transport)
    turn, usage = client.complete(
        messages=[{"role": "user", "content": "hi"}], tools=[]
    )
    assert captured["headers"]["Authorization"] == "Bearer secret-123"
    assert isinstance(turn, MessageTurn)


def test_client_missing_key_does_not_crash_at_import_but_at_call(monkeypatch):
    monkeypatch.delenv("FAKE_API_KEY", raising=False)
    client = ProviderClient(
        CFG,
        transport=lambda r: {
            "choices": [{"message": {"content": "x"}}],
            "usage": {"total_tokens": 1},
        },
    )
    # No key set: Authorization header is empty string, transport still injectable.
    turn, _ = client.complete(messages=[], tools=[])
    assert isinstance(turn, MessageTurn)


def test_cassette_replay(tmp_path: Path):
    cassette = {
        "choices": [{"message": {"role": "assistant", "content": "from cassette"}}],
        "usage": {"total_tokens": 5},
    }
    path = tmp_path / "c.json"
    path.write_text(json.dumps(cassette))

    def transport(_request):
        return json.loads(path.read_text())

    client = ProviderClient(CFG, transport=transport)
    turn, _ = client.complete(messages=[], tools=[])
    assert turn.content == "from cassette"
