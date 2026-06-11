from agent_eval_lab.tasks.schema import (
    AllOf,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    OutputMatchSpec,
    StateContains,
    StateEquals,
    TrajectorySpec,
)


def test_final_state_spec_holds_state_constraints() -> None:
    spec = FinalStateSpec(
        constraints=(
            StateEquals(path="tickets.T-1.status", expected="closed"),
            StateContains(path="docs.ids", expected="doc-1"),
        )
    )

    assert spec.type == "final_state"
    assert spec.constraints[0].path == "tickets.T-1.status"
    assert spec.constraints[1].expected == "doc-1"


def test_trajectory_spec_holds_trajectory_constraints() -> None:
    spec = TrajectorySpec(
        constraints=(
            NoToolCall(name="delete_ticket"),
            OnlyModifies(paths=("tickets.T-1",)),
            MaxToolCalls(n=3),
        )
    )

    assert spec.type == "trajectory"
    assert spec.constraints[0].name == "delete_ticket"
    assert spec.constraints[1].paths == ("tickets.T-1",)
    assert spec.constraints[2].n == 3


def test_all_of_nests_verification_specs_recursively() -> None:
    spec = AllOf(
        specs=(
            OutputMatchSpec(expected_output="done"),
            AllOf(specs=(FinalStateSpec(constraints=()),)),
        )
    )

    assert spec.type == "all_of"
    assert isinstance(spec.specs[1], AllOf)


def test_llm_judge_spec_defaults_scale_and_is_in_union() -> None:
    from agent_eval_lab.tasks.schema import LlmJudgeSpec, VerificationSpec

    spec = LlmJudgeSpec(
        rubric="Score fidelity.", judge_model="deepseek:deepseek-v4-pro"
    )

    assert spec.type == "llm_judge"
    assert spec.scale == (1, 5)
    assert isinstance(spec, VerificationSpec)


def test_execution_spec_shape_defaults_and_union_membership() -> None:
    import dataclasses

    import pytest

    from agent_eval_lab.tasks.schema import ExecutionSpec, VerificationSpec

    spec = ExecutionSpec(
        held_out_tests={"test_oracle.py": "def test_ok():\n    assert True\n"}
    )

    assert spec.type == "execution"
    assert spec.timeout_s is None
    assert isinstance(spec, VerificationSpec)
    assert [f.name for f in dataclasses.fields(ExecutionSpec)] == [
        "type",
        "held_out_tests",
        "timeout_s",
    ]
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.timeout_s = 5.0  # type: ignore[misc]
