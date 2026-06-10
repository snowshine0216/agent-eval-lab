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
