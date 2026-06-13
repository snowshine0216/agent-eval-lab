"""Tests for runners/history.py — bound the tool-result text fed to the provider.

The browse agent accumulates large page-text dumps; over many rounds the cumulative
tool-result content can exceed a model's context window (a real SiliconFlow 400 on
GLM-5.1 mid-D-run). trim_tool_result_history bounds what is SENT, newest-first.
"""

import json

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.runners.history import (
    ELISION_MARKER,
    trim_tool_result_history,
)
from agent_eval_lab.runners.wire import turn_to_message


def _tool_result(text: str, call_id: str) -> ToolResultTurn:
    return ToolResultTurn(
        call_id=call_id, outcome=ToolSuccess(result={"stdout": text, "exit_code": 0})
    )


def _content_len(turn: ToolResultTurn) -> int:
    return len(turn_to_message(turn)["content"])


def test_non_tool_turns_are_untouched() -> None:
    turns = (
        MessageTurn(role="system", content="sys"),
        MessageTurn(role="user", content="hello"),
        ToolCallTurn(
            content=None,
            tool_calls=(
                ToolCall(call_id="c1", name="bash", arguments={"command": "x"}),
            ),
        ),
    )
    assert trim_tool_result_history(turns, char_budget=10) == turns


def test_newest_tool_result_kept_even_if_it_alone_exceeds_budget() -> None:
    big = "X" * 5000
    turns = (_tool_result(big, "c1"),)
    out = trim_tool_result_history(turns, char_budget=100)
    # The single (newest) tool result is preserved in full — the model needs the
    # latest browse output to act on this round.
    assert out[0].outcome.result == {"stdout": big, "exit_code": 0}


def test_older_tool_results_elided_once_budget_exceeded() -> None:
    # Three browse dumps of ~2000 chars each; budget admits ~the newest two.
    turns = tuple(_tool_result("Y" * 2000, f"c{i}") for i in range(3))
    out = trim_tool_result_history(turns, char_budget=4500)
    # newest two kept in full; oldest elided.
    assert out[2].outcome.result == {"stdout": "Y" * 2000, "exit_code": 0}
    assert out[1].outcome.result == {"stdout": "Y" * 2000, "exit_code": 0}
    assert out[0].outcome.result == {"elided": ELISION_MARKER}


def test_total_sent_content_is_bounded_by_budget_plus_one_newest() -> None:
    turns = tuple(_tool_result("Z" * 3000, f"c{i}") for i in range(6))
    budget = 7000
    out = trim_tool_result_history(turns, char_budget=budget)
    kept = [t for t in out if t.outcome.result != {"elided": ELISION_MARKER}]
    # The kept (full) tool results, minus the always-kept newest, fit in the budget.
    non_newest_kept = sum(_content_len(t) for t in kept[:-1])
    assert non_newest_kept <= budget


def test_idempotent() -> None:
    turns = tuple(_tool_result("W" * 2000, f"c{i}") for i in range(4))
    once = trim_tool_result_history(turns, char_budget=4500)
    twice = trim_tool_result_history(once, char_budget=4500)
    assert once == twice


def test_elided_turns_serialize_small() -> None:
    turns = tuple(_tool_result("Q" * 4000, f"c{i}") for i in range(5))
    out = trim_tool_result_history(turns, char_budget=5000)
    elided = [t for t in out if t.outcome.result == {"elided": ELISION_MARKER}]
    assert elided, "expected at least one elided tool result"
    for t in elided:
        assert len(json.dumps(t.outcome.result)) < 100
