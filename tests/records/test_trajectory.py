from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.grade import GradeResult, RunResult
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn


def _trajectory(**overrides):
    defaults = dict(
        turns=(MessageTurn(role="user", content="hi"),),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.5),
        run_index=0,
        stop_reason="completed",
    )
    return Trajectory(**{**defaults, **overrides})


def test_trajectory_defaults_to_no_parse_failure() -> None:
    trajectory = _trajectory()

    assert trajectory.parse_failure is None
    assert trajectory.stop_reason == "completed"


def test_trajectory_records_parse_failure() -> None:
    failure = ParseFailure(raw='{"query": ', error="arguments not valid JSON")
    trajectory = _trajectory(stop_reason="parse_failure", parse_failure=failure)

    assert trajectory.parse_failure.error == "arguments not valid JSON"


def test_trajectory_defaults_to_no_final_state() -> None:
    trajectory = _trajectory()

    assert trajectory.final_state is None


def test_trajectory_records_final_state() -> None:
    trajectory = _trajectory(final_state={"tickets": {"T-1": {"status": "closed"}}})

    assert trajectory.final_state == {"tickets": {"T-1": {"status": "closed"}}}


def test_run_result_links_task_condition_and_grade() -> None:
    grade = GradeResult(
        grader_id="ast_tool_match",
        passed=True,
        score=1.0,
        evidence={},
        failure_reason=None,
    )
    run = RunResult(
        task_id="ws-001",
        condition_id="local:qwen3-8b",
        run_index=2,
        trajectory=_trajectory(run_index=2),
        grade=grade,
    )

    assert run.run_index == 2
    assert run.grade.passed is True


def test_trajectory_schema_version_defaults_to_2() -> None:
    assert _trajectory().schema_version == "2"


def test_trajectory_new_fields_default_safely() -> None:
    t = _trajectory()
    assert t.rounds == 0
    assert t.wall_time_s == 0.0
    assert t.tool_call_counts == {}
    assert t.safety_cap_bound is False
    assert t.env_health is None
    assert t.run_uid is None


def test_trajectory_accepts_new_stop_reasons() -> None:
    for reason in ("completed_natural", "safety_cap", "env_unhealthy"):
        assert _trajectory(stop_reason=reason).stop_reason == reason


def test_trajectory_records_env_health_and_counts() -> None:
    health = EnvHealth(
        pre_healthy=True, post_healthy=False, pre_status=200, post_status=503
    )
    t = _trajectory(
        stop_reason="env_unhealthy",
        rounds=3,
        wall_time_s=12.5,
        tool_call_counts={"bash": 7, "search_docs": 2},
        safety_cap_bound=False,
        env_health=health,
        run_uid="deepseek:deepseek-v4-pro__0003",
    )
    assert t.rounds == 3
    assert t.wall_time_s == 12.5
    assert t.tool_call_counts == {"bash": 7, "search_docs": 2}
    assert t.env_health == health
    assert t.run_uid == "deepseek:deepseek-v4-pro__0003"


def test_v1_compat_hydrates_legacy_dict_with_defaults() -> None:
    # A pre-revision trajectory dict: no schema_version, no new fields,
    # legacy stop_reason.
    legacy = {
        "turns": [MessageTurn(role="user", content="hi")],
        "usage": Usage(prompt_tokens=10, completion_tokens=5, latency_s=0.5),
        "run_index": 0,
        "stop_reason": "completed",
        "parse_failure": None,
        "final_state": None,
    }
    t = Trajectory.v1_compat(legacy)
    assert t.schema_version == "1"  # tagged as v1
    assert t.stop_reason == "completed"  # legacy value preserved as-is
    assert t.rounds == 0
    assert t.wall_time_s == 0.0
    assert t.tool_call_counts == {}
    assert t.safety_cap_bound is False
    assert t.env_health is None
    assert t.run_uid is None
    assert t.max_tokens is None
    assert t.parse_failure is None
    assert t.final_state is None


def test_v1_compat_preserves_legacy_max_steps_stop_reason() -> None:
    legacy = {
        "turns": [],
        "usage": Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        "run_index": 1,
        "stop_reason": "max_steps",
    }
    t = Trajectory.v1_compat(legacy)
    assert t.stop_reason == "max_steps"
    assert t.schema_version == "1"


def test_trajectory_accepts_max_rounds_stop_reason() -> None:
    assert _trajectory(stop_reason="max_rounds").stop_reason == "max_rounds"


def test_trajectory_round_policy_fields_default_safely() -> None:
    t = _trajectory(stop_reason="completed_natural")
    assert t.max_rounds is None
    assert t.safety_cap is None
    assert t.max_rounds_bound is False


def test_trajectory_records_round_policy_fields() -> None:
    t = _trajectory(
        stop_reason="max_rounds",
        max_rounds=20,
        safety_cap=200,
        max_rounds_bound=True,
    )
    assert t.max_rounds == 20
    assert t.safety_cap == 200
    assert t.max_rounds_bound is True
