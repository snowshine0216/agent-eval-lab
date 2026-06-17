from agent_eval_lab.records.trajectory import (
    PROVIDER_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.runners.b_live import (
    b_trial_run_uid,
    classify_invalid,
    run_b_arm,
)
from agent_eval_lab.tasks.schema import Task, TaskInput


def _task(task_id: str) -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id=task_id,
        capability="browser_mstr",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="build it"),),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def _ok(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=run_index,
        stop_reason="completed_natural",
        rounds=3,
    )


def _provider_fail(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="parse_failure",
        parse_failure=ParseFailure(raw="403", error=PROVIDER_ERROR),
    )


def _max_rounds(run_index: int) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
        run_index=run_index,
        stop_reason="max_rounds",
        rounds=50,
        max_rounds_bound=True,
    )


def test_run_uid_is_task_scoped() -> None:
    uid = b_trial_run_uid(
        condition_id="dashscope:qwen3.7-max", task_id="b-b1-noskill", run_index=2
    )
    assert uid == "dashscope:qwen3.7-max__b-b1-noskill__0002"


def test_provider_failure_is_invalid_max_rounds_is_not() -> None:
    assert classify_invalid(_provider_fail(0)) == "provider_error"
    # A max_rounds cap is a CENSORED task-failure, never invalid (spec §6.3).
    assert classify_invalid(_max_rounds(0)) is None
    assert classify_invalid(_ok(0)) is None


def test_run_b_arm_wraps_grade_less_btrials_with_save_names() -> None:
    seen: list[tuple[str, int, str]] = []

    def candidate_run_fn(task, run_index, save_name):
        seen.append((task.id, run_index, save_name))
        return _ok(run_index)

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.4,
    )
    assert outcome.void is False
    assert len(outcome.trials) == 3
    # Each trial carries its task-scoped save-name and NO grade.
    assert outcome.trials[0].save_name == ("dashscope-qwen3.7-max__b-b1-noskill__0000")
    assert all(not hasattr(t, "grade") for t in outcome.trials)
    assert all(t.invalid is False for t in outcome.trials)
    # The candidate driver was handed the rendered save-name per trial.
    assert seen[0][2] == "dashscope-qwen3.7-max__b-b1-noskill__0000"


def test_run_b_arm_replaces_provider_invalid_until_k_valid() -> None:
    scripted = [_provider_fail(0), _ok(1), _ok(2), _ok(3)]
    calls = [0]

    def candidate_run_fn(task, run_index, save_name):
        traj = scripted[calls[0]]
        calls[0] += 1
        return traj

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.5,
    )
    assert outcome.void is False
    assert len(outcome.trials) == 3  # only VALID trials are banked
    # The invalid attempt is recorded in attempts with its reason.
    invalid = [t for t in outcome.all_trials if t.invalid]
    assert len(invalid) == 1
    assert invalid[0].invalid_reason == "provider_error"


def test_run_b_arm_voids_when_invalid_rate_exceeded() -> None:
    def candidate_run_fn(task, run_index, save_name):
        return _provider_fail(run_index)

    outcome = run_b_arm(
        task=_task("b-b1-noskill"),
        condition_id="dashscope:qwen3.7-max",
        folder="/Candidate/bxu",
        candidate_run_fn=candidate_run_fn,
        k_valid=3,
        max_invalid_rate=0.4,
    )
    assert outcome.void is True
    assert len(outcome.trials) < 3
