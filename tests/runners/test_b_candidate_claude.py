import json
import subprocess

import pytest

from agent_eval_lab.records.trajectory import PROVIDER_ERROR
from agent_eval_lab.runners.b_candidate_claude import make_b_claude_run_fn
from agent_eval_lab.tasks.schema import Task, TaskInput


class _FakeCompleted:
    def __init__(self, *, stdout="", stderr="", returncode=0):
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode


def _task() -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Build the B-1 report."),),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),  # live path never grades; minimal valid spec
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def _result_json(*, num_turns=6, total_cost_usd=0.0321, is_error=False):
    return json.dumps(
        {
            "usage": {"input_tokens": 100, "output_tokens": 50},
            "num_turns": num_turns,
            "total_cost_usd": total_cost_usd,
            "is_error": is_error,
        }
    )


def test_claude_run_fn_success_records_turns_and_cost(tmp_path) -> None:
    captured = {}

    def fake_subprocess(argv, *, cwd, env, timeout):
        captured["argv"] = argv
        captured["env"] = env
        return _FakeCompleted(stdout=_result_json())

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
    )
    traj = run_fn(_task(), 1, "claude-cli-claude-sonnet-4-6__b-b1-skill__0001")
    assert traj.stop_reason == "completed_natural"
    assert traj.rounds == 6
    assert traj.total_cost_usd == 0.0321
    # The rendered prompt (last argv element) carries the save-name + folder.
    assert "claude-cli-claude-sonnet-4-6__b-b1-skill__0001" in captured["argv"][-1]
    assert "/Candidate/bxu" in captured["argv"][-1]
    # Bash is allowed for the live browser surface (not edit-only).
    assert "Bash" in " ".join(captured["argv"])


def test_claude_run_fn_nonzero_exit_is_env_invalid(tmp_path) -> None:
    def fake_subprocess(argv, *, cwd, env, timeout):
        return _FakeCompleted(stdout="", stderr="boom", returncode=1)

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    traj = run_fn(_task(), 0, "save0")
    assert traj.stop_reason == "env_unhealthy"
    assert traj.parse_failure is not None
    assert traj.parse_failure.error == PROVIDER_ERROR


def test_claude_run_fn_timeout_is_env_invalid(tmp_path) -> None:
    def fake_subprocess(argv, *, cwd, env, timeout):
        raise subprocess.TimeoutExpired(cmd="claude", timeout=timeout)

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    traj = run_fn(_task(), 0, "save0")
    assert traj.stop_reason == "env_unhealthy"


def test_claude_run_fn_raises_on_task_with_no_user_message(tmp_path) -> None:
    """P1-1: a task with no user-role message must raise ValueError, not silently
    render an empty prompt into the claude -p argv."""
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskInput, TaskMetadata

    no_user_task = Task(
        id="b-b1-skill",
        capability="browser_mstr",
        input=TaskInput(
            messages=(MessageTurn(role="system", content="sys only"),),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )

    def fake_subprocess(argv, *, cwd, env, timeout):
        raise AssertionError("subprocess should not be called")

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    with pytest.raises(ValueError, match="no user message"):
        run_fn(no_user_task, 0, "save0")


def test_claude_run_fn_none_stdout_degrades_to_env_invalid(tmp_path) -> None:
    """A CompletedProcess-like object with stdout=None (e.g. from bare subprocess.run
    without capture_output=True) must degrade to env-invalid, not crash."""

    class _NullStdout:
        returncode = 0
        stdout = None
        stderr = ""

    def fake_subprocess(argv, *, cwd, env, timeout):
        return _NullStdout()

    run_fn = make_b_claude_run_fn(
        model="claude-sonnet-4-6",
        run_subprocess=fake_subprocess,
        workdir_factory=lambda: tmp_path,
        login=("u", "bxu"),
        folder="/f",
    )
    traj = run_fn(_task(), 0, "save0")
    assert traj.stop_reason == "env_unhealthy"
