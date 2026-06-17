from agent_eval_lab.records.b_trial import (
    BTrial,
    b_trial_from_dict,
    b_trial_to_dict,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage


def _traj() -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=10, completion_tokens=5, latency_s=1.0),
        run_index=2,
        stop_reason="completed_natural",
        rounds=7,
        wall_time_s=12.5,
        run_uid="dashscope-qwen3.7-max__b-b1-noskill__0002",
    )


def test_btrial_is_frozen_and_grade_less() -> None:
    trial = BTrial(
        run_uid="dashscope-qwen3.7-max__b-b1-noskill__0002",
        condition_id="dashscope:qwen3.7-max",
        task_id="b-b1-noskill",
        save_name="dashscope-qwen3.7-max__b-b1-noskill__0002",
        folder="/Candidate/bxu",
        trajectory=_traj(),
        invalid=False,
        invalid_reason=None,
    )
    assert not hasattr(trial, "grade")
    import dataclasses

    try:
        trial.invalid = True  # type: ignore[misc]
        raise AssertionError("BTrial must be frozen")
    except dataclasses.FrozenInstanceError:
        pass


def test_btrial_round_trips_through_dict() -> None:
    trial = BTrial(
        run_uid="dashscope-qwen3.7-max__b-b1-skill__0001",
        condition_id="dashscope:qwen3.7-max",
        task_id="b-b1-skill",
        save_name="dashscope-qwen3.7-max__b-b1-skill__0001",
        folder="/Candidate/bxu",
        trajectory=_traj(),
        invalid=True,
        invalid_reason="provider_error",
    )
    restored = b_trial_from_dict(b_trial_to_dict(trial))
    assert restored == trial
    # invalid_reason and the trajectory survive the round-trip.
    assert restored.invalid_reason == "provider_error"
    assert restored.trajectory.rounds == 7
