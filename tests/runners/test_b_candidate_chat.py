from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.b_candidate_chat import make_b_chat_run_fn
from agent_eval_lab.tasks.schema import Task, TaskInput


def _task() -> Task:
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import AllOf, TaskMetadata

    return Task(
        id="b-b1-noskill",
        capability="browser_mstr",
        input=TaskInput(
            messages=(
                MessageTurn(role="system", content="sys"),
                MessageTurn(role="user", content="Build the B-1 report."),
            ),
            available_tools=("bash",),
        ),
        verification=AllOf(specs=()),  # live path never grades; minimal valid spec
        metadata=TaskMetadata(
            split="held_out", version="b-domain-v1", provenance="test"
        ),
        initial_state={"task_key": "B-1"},
    )


def test_chat_run_fn_wires_browse_loop_with_rendered_save_name(tmp_path) -> None:
    captured = {}

    def fake_run_single(**kwargs):
        captured.update(kwargs)
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=1, completion_tokens=1, latency_s=0.0),
            run_index=kwargs["run_index"],
            stop_reason="completed_natural",
            rounds=4,
        )

    closes = []

    def fake_executor_factory(*, session_id, workdir):
        def executor(req):  # never called by the fake run_single
            raise AssertionError("executor should not run under a fake run_single")

        closes.append(session_id)
        return executor, lambda: None

    run_fn = make_b_chat_run_fn(
        config=object(),  # opaque; the fake run_single ignores it
        http_client=object(),
        temperature=0.0,
        max_tokens=4096,
        condition_id="dashscope:qwen3.7-max",
        login=("https://lab/app", "bxu"),
        folder="/Candidate/bxu",
        workdir_root=tmp_path,
        executor_factory=fake_executor_factory,
        run_single_fn=fake_run_single,
    )
    traj = run_fn(_task(), 2, "dashscope-qwen3.7-max__b-b1-noskill__0002")

    assert traj.rounds == 4
    # browse-world registry + the 50-round cap + the task-scoped run_uid.
    from agent_eval_lab.tools.browse import BROWSE_TOOLS

    assert captured["registry"] is BROWSE_TOOLS
    assert captured["max_rounds"] == 50
    assert captured["run_uid"] == "dashscope:qwen3.7-max__b-b1-noskill__0002"
    # The rendered user message carries the save-name + folder + app url.
    rebuilt = captured["task"]
    user = next(m for m in rebuilt.input.messages if m.role == "user")
    assert "dashscope-qwen3.7-max__b-b1-noskill__0002" in user.content
    assert "/Candidate/bxu" in user.content
    assert "https://lab/app" in user.content
    # The system message is preserved (skill arm injection lives upstream).
    assert any(
        m.role == "system" and m.content == "sys" for m in rebuilt.input.messages
    )


def test_chat_run_fn_closes_the_executor(tmp_path) -> None:
    closed = []

    def fake_run_single(**kwargs):
        return Trajectory(
            turns=(),
            usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
            run_index=0,
            stop_reason="completed_natural",
        )

    def fake_executor_factory(*, session_id, workdir):
        return (lambda req: None), (lambda: closed.append(session_id))

    run_fn = make_b_chat_run_fn(
        config=object(),
        http_client=object(),
        temperature=0.0,
        max_tokens=4096,
        condition_id="c",
        login=("u", "bxu"),
        folder="/f",
        workdir_root=tmp_path,
        executor_factory=fake_executor_factory,
        run_single_fn=fake_run_single,
    )
    run_fn(_task(), 0, "save0")
    assert closed  # the per-trial executor was closed even on the happy path
