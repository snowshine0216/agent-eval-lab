from agent_eval_lab.tasks.codec import to_dict
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.loader import load_tasks, write_run_results
from agent_eval_lab.tasks.task import Task, TaskInput, TaskMetadata
from agent_eval_lab.tasks.tool_calls import ExpectedToolCall
from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import ToolCallMatchSpec


def _task(task_id):
    return Task(
        id=task_id,
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="hi"),),
            available_tools=({"name": "search_docs"},),
        ),
        verification=ToolCallMatchSpec(
            expected_tool_calls=(ExpectedToolCall(name="search_docs"),),
        ),
        metadata=TaskMetadata(
            split="dev",
            version="1",
            provenance="handwritten",
            world_template_id="workspace",
            difficulty_knob="baseline",
        ),
    )


def test_load_tasks_reads_jsonl(tmp_path):
    path = tmp_path / "tasks.jsonl"
    lines = [to_dict(_task("a")), to_dict(_task("b"))]
    import json

    path.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    tasks = load_tasks(path)
    assert [t.id for t in tasks] == ["a", "b"]


def test_write_run_results_roundtrips(tmp_path):
    path = tmp_path / "runs.jsonl"
    traj = Trajectory(
        turns=(MessageTurn(role="assistant", content="x"),),
        usage={"total_tokens": 1},
        cost_usd=0.0,
        latency_ms=1,
        run_index=0,
        termination_reason="stop",
    )
    rr = RunResult(
        task_id="a",
        condition_id="c",
        run_index=0,
        trajectory=traj,
        grade=GradeResult(grader_id="g", passed=True, score=1.0),
    )
    write_run_results(path, [rr])
    from agent_eval_lab.tasks.loader import load_run_results

    loaded = load_run_results(path)
    assert loaded == [rr]
