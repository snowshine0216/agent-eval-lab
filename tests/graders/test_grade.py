import pytest

from agent_eval_lab.graders.grade import grade_trajectory
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall, ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn
from agent_eval_lab.tasks.verification import OutputMatchSpec, ToolCallMatchSpec
from agent_eval_lab.tools.workspace_world import TOOL_SCHEMAS


def test_tool_call_match_dispatch_passes():
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        ),
    )
    turns = (
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
            )
        ),
    )
    result = grade_trajectory(spec, turns, TOOL_SCHEMAS)
    assert result.passed is True


def test_output_match_dispatch_uses_last_assistant_message():
    spec = OutputMatchSpec(expected_output="42")
    turns = (MessageTurn(role="assistant", content="42"),)
    result = grade_trajectory(spec, turns, TOOL_SCHEMAS)
    assert result.passed is True
    assert result.grader_id == "output_match"


def test_unsupported_spec_type_raises():
    class FakeSpec:
        type = "final_state"

    with pytest.raises(Exception) as exc:
        grade_trajectory(FakeSpec(), (), TOOL_SCHEMAS)
    assert "not implemented" in str(exc.value)
