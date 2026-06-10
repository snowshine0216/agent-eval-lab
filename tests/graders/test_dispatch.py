import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolCall, ToolCallTurn
from agent_eval_lab.tasks.schema import (
    AllOf,
    ExpectedToolCall,
    FinalStateSpec,
    NoToolCall,
    OutputMatchSpec,
    StateEquals,
    ToolCallMatchSpec,
    TrajectorySpec,
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


def _state_trajectory(final_state, *turns):
    return Trajectory(
        turns=turns,
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state=final_state,
    )


def test_dispatches_final_state_spec() -> None:
    spec = FinalStateSpec(
        constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
    )
    trajectory = _state_trajectory({"tickets": {"T-1": {"status": "closed"}}})

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is True
    assert result.grader_id == "final_state"


def test_dispatches_trajectory_spec() -> None:
    spec = TrajectorySpec(constraints=(NoToolCall(name="update_ticket"),))
    trajectory = _state_trajectory(
        None,
        ToolCallTurn(
            tool_calls=(ToolCall(call_id="c", name="update_ticket", arguments={}),)
        ),
    )

    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )

    assert result.passed is False
    assert result.failure_reason == "forbidden_action"


def test_dispatches_all_of_threading_registry_and_initial_state() -> None:
    spec = AllOf(
        specs=(
            ToolCallMatchSpec(
                expected_tool_calls=(
                    ExpectedToolCall(name="search_docs", arguments={"query": "x"}),
                )
            ),
            FinalStateSpec(
                constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
            ),
        )
    )
    trajectory = _state_trajectory(
        {"tickets": {"T-1": {"status": "closed"}}},
        ToolCallTurn(
            tool_calls=(
                ToolCall(call_id="c", name="search_docs", arguments={"query": "x"}),
            )
        ),
    )

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        initial_state=None,
    )

    assert result.passed is True
    assert result.grader_id == "all_of"
    assert len(result.evidence["sub_results"]) == 2


def test_unknown_spec_still_raises() -> None:
    class _Unknown:
        pass

    with pytest.raises(ValueError, match="unsupported verification spec"):
        grade_trajectory(
            verification=_Unknown(),  # type: ignore[arg-type]
            trajectory=_state_trajectory(None),
            registry=WORKSPACE_TOOLS,
        )


def test_dispatches_llm_judge_with_supplied_verdict() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    spec = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    h = prompt_hash(build_judge_prompt(spec=spec, trajectory=trajectory))
    verdict = JudgeVerdict(
        score=5, rationale="ok", raw="SCORE: 5", judge_model="m", prompt_hash=h
    )

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={h: verdict},
    )

    assert result.passed is True
    assert result.grader_id == "llm_judge"


def test_all_of_with_judge_leg_runs_deterministic_leg_regardless() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    judge = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    spec = AllOf(
        specs=(
            FinalStateSpec(
                constraints=(StateEquals(path="tickets.T-1.status", expected="closed"),)
            ),
            judge,
        )
    )
    trajectory = _state_trajectory({"tickets": {"T-1": {"status": "closed"}}})
    h = prompt_hash(build_judge_prompt(spec=judge, trajectory=trajectory))
    # judge fails (score 2) but the deterministic leg passes -> AllOf fails
    verdict = JudgeVerdict(
        score=2, rationale="bad", raw="SCORE: 2", judge_model="m", prompt_hash=h
    )

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={h: verdict},
    )

    assert result.passed is False
    subs = result.evidence["sub_results"]
    assert len(subs) == 2
    assert subs[0]["grader_id"] == "final_state" and subs[0]["passed"] is True
    assert subs[1]["grader_id"] == "llm_judge" and subs[1]["passed"] is False


def test_existing_dispatch_works_with_default_empty_verdicts() -> None:
    spec = OutputMatchSpec(expected_output="Done.")
    trajectory = _trajectory(MessageTurn(role="assistant", content="Done."))
    result = grade_trajectory(
        verification=spec, trajectory=trajectory, registry=WORKSPACE_TOOLS
    )
    assert result.passed is True


def test_dispatch_module_imports_no_http_client() -> None:
    import agent_eval_lab.graders.dispatch as dispatch_mod

    src = open(dispatch_mod.__file__).read()
    assert "httpx" not in src
    assert "chat_completion" not in src
