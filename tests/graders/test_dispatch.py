import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import (
    ExpectedToolCall,
    OutputMatchSpec,
    ToolCallMatchSpec,
)
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS


def _trajectory(*turns) -> Trajectory:
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )


def test_dispatches_output_match_to_final_assistant_message() -> None:
    trajectory = _trajectory(
        MessageTurn(role="user", content="Say done."),
        MessageTurn(role="assistant", content="Done."),
    )
    spec = OutputMatchSpec(expected_output="Done.")

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "output_match"


def test_output_match_fails_when_no_assistant_message() -> None:
    trajectory = _trajectory(MessageTurn(role="user", content="Say done."))
    spec = OutputMatchSpec(expected_output="Done.")

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is False
    assert result.evidence == {"error": "no assistant message in trajectory"}


def test_output_match_rejects_unsupported_normalizer() -> None:
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    spec = OutputMatchSpec(expected_output="Done.", normalizer="lowercase")

    with pytest.raises(ValueError, match="unsupported normalizer"):
        grade_trajectory(
            verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
        )


def test_dispatches_tool_call_match() -> None:
    trajectory = _trajectory(
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c1", name="search_docs", arguments={"query": "x"}),
            )
        )
    )
    spec = ToolCallMatchSpec(
        expected_tool_calls=(
            ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
        )
    )

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "ast_tool_match"
