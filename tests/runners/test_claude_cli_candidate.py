# tests/runners/test_claude_cli_candidate.py
import json
import pytest
from agent_eval_lab.runners.claude_cli_candidate import (
    ClaudeRunMeta,
    ClaudeResultParseError,
    parse_claude_result,
)


def _result_json(**over):
    base = {
        "type": "result",
        "subtype": "success",
        "is_error": False,
        "num_turns": 7,
        "total_cost_usd": 0.0123,
        "usage": {"input_tokens": 1500, "output_tokens": 320},
        "result": "done",
    }
    base.update(over)
    return json.dumps(base)


def test_parse_happy_path_maps_usage_and_turns():
    meta = parse_claude_result(_result_json())
    assert meta == ClaudeRunMeta(
        prompt_tokens=1500,
        completion_tokens=320,
        num_turns=7,
        total_cost_usd=0.0123,
        is_error=False,
    )


def test_parse_is_error_true_is_carried():
    meta = parse_claude_result(_result_json(is_error=True, subtype="error_max_turns"))
    assert meta.is_error is True


def test_parse_malformed_json_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result("not json {")


def test_parse_missing_usage_raises_typed_error():
    with pytest.raises(ClaudeResultParseError):
        parse_claude_result(json.dumps({"type": "result", "is_error": False}))
