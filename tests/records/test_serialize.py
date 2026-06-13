from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.serialize import (
    grade_result_to_dict,
    run_result_to_dict,
    trajectory_from_dict,
    trajectory_to_dict,
    turn_from_dict,
    turn_to_dict,
)
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolFailure,
    ToolResultTurn,
    ToolSuccess,
)

TURNS = (
    MessageTurn(role="user", content="Close ticket T-7."),
    ToolCallTurn(
        tool_calls=(
            ToolCall(
                call_id="c1",
                name="update_ticket",
                arguments={"ticket_id": "T-7", "status": "closed"},
            ),
        ),
        content=None,
    ),
    ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ticket_id": "T-7"})),
    ToolResultTurn(call_id="c2", outcome=ToolFailure(error="unknown ticket_id: T-9")),
    MessageTurn(role="assistant", content="Done."),
)


def test_every_turn_variant_round_trips() -> None:
    for turn in TURNS:
        assert turn_from_dict(turn_to_dict(turn)) == turn


def test_trajectory_round_trips_including_parse_failure() -> None:
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=12, completion_tokens=7, latency_s=0.25),
        run_index=1,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw='{"q": ', error="bad json"),
    )

    assert trajectory_from_dict(trajectory_to_dict(trajectory)) == trajectory


def test_trajectory_from_dict_applies_defaults() -> None:
    trajectory = trajectory_from_dict(
        {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
    )

    assert trajectory.usage == Usage(
        prompt_tokens=0, completion_tokens=0, latency_s=0.0
    )
    assert trajectory.run_index == 0
    assert trajectory.stop_reason == "completed"
    assert trajectory.parse_failure is None


def test_run_result_to_dict_is_json_shaped() -> None:
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=0,
        trajectory=trajectory_from_dict(
            {"turns": [{"type": "message", "role": "user", "content": "hi"}]}
        ),
        grade=GradeResult(
            grader_id="ast_tool_match",
            passed=False,
            score=0.0,
            evidence={"error": "x"},
            failure_reason="wrong_tool",
        ),
    )
    data = run_result_to_dict(run)

    assert data["task_id"] == "ws-001"
    assert data["grade"]["failure_reason"] == "wrong_tool"
    assert data["trajectory"]["turns"][0]["type"] == "message"


def test_grade_result_to_dict_keeps_none_failure_reason() -> None:
    grade = GradeResult(grader_id="output_match", passed=True, score=1.0, evidence={})

    assert grade_result_to_dict(grade)["failure_reason"] is None


def test_trajectory_to_dict_omits_final_state_when_none() -> None:
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=1, completion_tokens=2, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
    )

    data = trajectory_to_dict(trajectory)

    assert data["final_state"] is None


def test_trajectory_round_trips_final_state() -> None:
    state = {"tickets": {"T-1": {"status": "closed"}}}
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=1, completion_tokens=2, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
        final_state=state,
    )

    restored = trajectory_from_dict(trajectory_to_dict(trajectory))

    assert restored.final_state == state


def test_trajectory_final_state_with_nested_mappingproxytype_is_json_serializable() -> (
    None
):
    """Nested MappingProxyType (and tuples) must deep-convert to plain dicts/lists
    so json.dumps never raises, and the round-trip value equals the plain-Python
    equivalent structure."""
    import json
    import types

    nested_proxy = types.MappingProxyType({"status": "open", "tags": ("bug", "urgent")})
    state = types.MappingProxyType(
        {"tickets": types.MappingProxyType({"T-1": nested_proxy})}
    )
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=1, completion_tokens=2, latency_s=0.1),
        run_index=0,
        stop_reason="completed",
        final_state=state,
    )

    data = trajectory_to_dict(trajectory)
    # Must not raise TypeError
    serialized = json.dumps(data)
    assert serialized  # non-empty

    restored = trajectory_from_dict(data)
    expected = {"tickets": {"T-1": {"status": "open", "tags": ["bug", "urgent"]}}}
    assert restored.final_state == expected


def test_judge_verdict_round_trips() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict

    v = JudgeVerdict(
        score=4, rationale="r", raw="SCORE: 4", judge_model="m", prompt_hash="h"
    )
    assert verdict_from_dict(verdict_to_dict(v)) == v


def test_judge_error_round_trips() -> None:
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict
    from agent_eval_lab.runners.judge_edge import JudgeError

    e = JudgeError(kind="http", error="500", prompt_hash="h", judge_model="m")
    assert verdict_from_dict(verdict_to_dict(e)) == e


def test_execution_verdict_round_trips_under_its_own_tag() -> None:
    import json

    from agent_eval_lab.graders.execution import ExecutionVerdict
    from agent_eval_lab.records.execution import ExecutionResult, TestCaseResult
    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict

    v = ExecutionVerdict(
        result=ExecutionResult(
            status="failed",
            exit_code=1,
            passed=1,
            failed=1,
            errors=0,
            skipped=0,
            tests=(
                TestCaseResult(test_id="test_calc::test_add", status="failed"),
                TestCaseResult(test_id="test_calc::test_zero", status="passed"),
            ),
            stdout="1 failed, 1 passed in <duration>",
            stderr="",
        ),
        execution_hash="deadbeef",
        displaced_paths=("tests/test_app.py",),
    )
    data = verdict_to_dict(v)
    assert data["type"] == "execution_verdict"
    assert json.loads(json.dumps(data)) == data
    assert verdict_from_dict(data) == v


def test_execution_error_round_trips_under_its_own_tag() -> None:
    import json

    from agent_eval_lab.records.serialize import verdict_from_dict, verdict_to_dict
    from agent_eval_lab.runners.oracle_edge import ExecutionError

    e = ExecutionError(
        kind="tree_collision",
        detail="agent 'Tests/a' vs oracle 'tests/a'",
        execution_hash="deadbeef",
    )
    data = verdict_to_dict(e)
    assert data["type"] == "execution_error"
    assert json.loads(json.dumps(data)) == data
    assert verdict_from_dict(data) == e


def test_verdict_from_dict_missing_type_raises_value_error() -> None:
    # Missing "type" key must raise ValueError (same family as unknown type),
    # not KeyError (which would expose an implementation detail).
    import pytest

    from agent_eval_lab.records.serialize import verdict_from_dict

    with pytest.raises(ValueError, match="type"):
        verdict_from_dict({"score": 3})


def test_verdict_from_dict_unknown_type_raises_value_error() -> None:
    import pytest

    from agent_eval_lab.records.serialize import verdict_from_dict

    with pytest.raises(ValueError, match="unknown verdict value type"):
        verdict_from_dict({"type": "nonexistent_type"})


def test_judge_legacy_verdict_tag_is_frozen() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict
    from agent_eval_lab.records.serialize import verdict_to_dict

    v = JudgeVerdict(
        score=4, rationale="r", raw="SCORE: 4", judge_model="m", prompt_hash="h"
    )
    # Renaming the legacy tag would break round-trips of existing artifacts.
    assert verdict_to_dict(v)["type"] == "verdict"


def test_trajectory_round_trips_all_new_fields() -> None:
    health = EnvHealth(
        pre_healthy=True, post_healthy=False, pre_status=200, post_status=503
    )
    trajectory = Trajectory(
        turns=TURNS,
        usage=Usage(prompt_tokens=12, completion_tokens=7, latency_s=0.25),
        run_index=2,
        stop_reason="env_unhealthy",
        rounds=4,
        wall_time_s=9.5,
        tool_call_counts={"bash": 3, "search_docs": 1},
        safety_cap_bound=False,
        env_health=health,
        run_uid="deepseek:deepseek-v4-pro__0002",
        max_tokens=4096,
    )
    restored = trajectory_from_dict(trajectory_to_dict(trajectory))
    assert restored == trajectory
    assert restored.schema_version == "2"


def test_safety_cap_trajectory_round_trips() -> None:
    trajectory = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.1),
        run_index=0,
        stop_reason="safety_cap",
        rounds=200,
        tool_call_counts={"bash": 200},
        safety_cap_bound=True,
    )
    restored = trajectory_from_dict(trajectory_to_dict(trajectory))
    assert restored.stop_reason == "safety_cap"
    assert restored.safety_cap_bound is True


def test_v1_dict_without_schema_version_loads_as_v1_with_defaults() -> None:
    # Exactly the on-disk shape of docs/2026-06-11-coding-agent-eval/runs/*.jsonl.
    v1 = {
        "turns": [{"type": "message", "role": "user", "content": "hi"}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "latency_s": 0.5},
        "run_index": 0,
        "stop_reason": "completed",
        "parse_failure": None,
        "final_state": None,
    }
    t = trajectory_from_dict(v1)
    assert t.schema_version == "1"
    assert t.rounds == 0
    assert t.tool_call_counts == {}
    assert t.env_health is None
    assert t.run_uid is None
    assert t.safety_cap_bound is False


def test_v2_dict_round_trip_is_idempotent_on_disk_keys() -> None:
    health = EnvHealth(
        pre_healthy=False, post_healthy=False, pre_status=None, post_status=503
    )
    trajectory = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="env_unhealthy",
        env_health=health,
        run_uid="local:qwen3-8b__0000",
    )
    d = trajectory_to_dict(trajectory)
    assert d["schema_version"] == "2"
    assert d["env_health"] == {
        "pre_healthy": False,
        "post_healthy": False,
        "pre_status": None,
        "post_status": 503,
    }
    assert d["run_uid"] == "local:qwen3-8b__0000"
    assert d["tool_call_counts"] == {}
