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


_EXEC_ORACLE = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
}
_EXEC_TREE = {"calc.py": "def add(a, b):\n    return a + b\n"}


def _execution_fixture():
    from agent_eval_lab.graders.execution import ExecutionVerdict, execution_hash
    from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
    from agent_eval_lab.tasks.schema import ExecutionSpec

    spec = ExecutionSpec(held_out_tests=_EXEC_ORACLE)
    key = execution_hash(spec, _EXEC_TREE)
    verdict = ExecutionVerdict(
        result=ExecutionResult(
            status="passed",
            exit_code=0,
            passed=1,
            failed=0,
            errors=0,
            skipped=0,
            tests=(
                TestCaseResult(test_id="test_oracle_calc::test_add", status="passed"),
            ),
            stdout="1 passed in <duration>",
            stderr="",
        ),
        execution_hash=key,
        displaced_paths=(),
    )
    return spec, key, verdict


def test_dispatches_execution_spec_with_supplied_verdict() -> None:
    spec, key, verdict = _execution_fixture()
    trajectory = _state_trajectory({"files": _EXEC_TREE})

    result = grade_trajectory(
        verification=spec,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={key: verdict},
    )

    assert result.passed is True
    assert result.grader_id == "execution"


def test_all_of_grades_execution_leg_beside_policy_leg() -> None:
    spec, key, verdict = _execution_fixture()
    composite = AllOf(
        specs=(spec, TrajectorySpec(constraints=(NoToolCall(name="run_tests"),)))
    )
    trajectory = _state_trajectory({"files": _EXEC_TREE})

    result = grade_trajectory(
        verification=composite,
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts={key: verdict},
    )

    assert result.passed is True
    subs = result.evidence["sub_results"]
    assert [sub["grader_id"] for sub in subs] == ["execution", "trajectory_policy"]
    assert all(sub["passed"] for sub in subs)


def test_judge_and_execution_verdicts_coexist_in_one_map() -> None:
    from agent_eval_lab.graders.judge import (
        JudgeVerdict,
        build_judge_prompt,
        prompt_hash,
    )
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    exec_spec, exec_key, exec_verdict = _execution_fixture()
    judge_spec = LlmJudgeSpec(rubric="r", judge_model="m", scale=(1, 5))
    trajectory = _state_trajectory(
        {"files": _EXEC_TREE}, MessageTurn(role="assistant", content="Done.")
    )
    judge_key = prompt_hash(build_judge_prompt(spec=judge_spec, trajectory=trajectory))
    judge_verdict = JudgeVerdict(
        score=5,
        rationale="ok",
        raw="SCORE: 5",
        judge_model="m",
        prompt_hash=judge_key,
    )
    verdicts = {exec_key: exec_verdict, judge_key: judge_verdict}

    result = grade_trajectory(
        verification=AllOf(specs=(exec_spec, judge_spec)),
        trajectory=trajectory,
        registry=WORKSPACE_TOOLS,
        verdicts=verdicts,
    )

    assert result.passed is True
    subs = result.evidence["sub_results"]
    assert [sub["grader_id"] for sub in subs] == ["execution", "llm_judge"]
