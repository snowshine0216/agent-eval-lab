import json

import httpx

from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.multi_run import run_task_k
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tasks.schema import (
    OnlyModifies,
    Task,
    TaskInput,
    TaskMetadata,
    TrajectorySpec,
)
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

CONFIG = ProviderConfig(
    id="local",
    base_url="http://localhost:11434/v1",
    api_key_env="",
    model_id="qwen3-8b",
)

TASK = parse_task(
    {
        "id": "ws-001",
        "capability": "tool_selection",
        "input": {
            "messages": [
                {
                    "type": "message",
                    "role": "user",
                    "content": "Search the docs for 'refund policy'.",
                }
            ],
            "available_tools": ["search_docs", "create_ticket", "update_ticket"],
        },
        "verification": {
            "type": "tool_call_match",
            "expected_tool_calls": [
                {"name": "search_docs", "arguments": {"query": "refund policy"}}
            ],
            "match": "exact_sequence",
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {"docs": {}, "tickets": {}},
    }
)


def _handler(request: httpx.Request) -> httpx.Response:
    body = json.loads(request.content)
    if any(message["role"] == "tool" for message in body["messages"]):
        message = {"role": "assistant", "content": "Done."}
    else:
        message = {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "c1",
                    "type": "function",
                    "function": {
                        "name": "search_docs",
                        "arguments": json.dumps({"query": "refund policy"}),
                    },
                }
            ],
        }
    return httpx.Response(
        200,
        json={
            "choices": [{"message": message}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


def test_run_task_k_grades_final_state_spec() -> None:
    """Verify initial_state is threaded: OnlyModifies(paths=()) forbids any change."""
    from agent_eval_lab.records.turns import MessageTurn

    responses = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {
                                    "name": "create_ticket",
                                    "arguments": json.dumps(
                                        {"title": "Bug", "priority": "low"}
                                    ),
                                },
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        {
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    ]
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    # initial_state has T-1 open; the run creates T-2.
    # With initial_state threaded: T-2 is a new leaf, T-1.status is unchanged.
    #   Only T-2.* changed -> covered by paths=("tickets.T-2",) -> passes.
    # Without threading (initial_state=None): T-1.status also looks "added"
    #   -> violation -> fails. This discriminates the two code paths.
    task = Task(
        id="ws-init-state",
        capability="tool_selection",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Create a ticket."),),
            available_tools=("create_ticket",),
        ),
        verification=TrajectorySpec(
            constraints=(OnlyModifies(paths=("tickets.T-2",)),)
        ),
        metadata=TaskMetadata(split="dev", version="1", provenance="hand_written"),
        initial_state={"tickets": {"T-1": {"status": "open"}}},
    )

    results = run_task_k(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        k=1,
        max_steps=4,
        temperature=0.0,
    )

    # With initial_state threaded, only T-2.* changed and it is covered.
    assert results[0].grade.passed is True


def test_effective_max_steps_prefers_per_task_budget() -> None:
    from agent_eval_lab.runners.multi_run import effective_max_steps

    task = parse_task(
        {
            "id": "ws2-020",
            "capability": "multi_step_state",
            "input": {
                "messages": [{"type": "message", "role": "user", "content": "go"}],
                "available_tools": ["search_docs"],
            },
            "verification": {
                "type": "final_state",
                "constraints": [{"type": "state_equals", "path": "x", "expected": 1}],
            },
            "metadata": {
                "split": "dev",
                "version": "2",
                "provenance": "hand_written",
                "max_steps": 6,
            },
        }
    )
    # Per-task budget wins over a lower CLI default.
    assert effective_max_steps(task, default=4) == 6


def test_effective_max_steps_falls_back_to_default_when_absent() -> None:
    from agent_eval_lab.runners.multi_run import effective_max_steps

    # TASK (module-level) carries no metadata.max_steps -> falls back to default.
    assert effective_max_steps(TASK, default=6) == 6


def _counting_tool_call_handler(counter: list[int]):
    """Always returns a tool call (never a final message), so the loop runs to
    exhaustion. Each call increments the counter -> counts loop iterations."""

    def handler(request: httpx.Request) -> httpx.Response:
        counter[0] += 1
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": f"c{counter[0]}",
                                    "type": "function",
                                    "function": {
                                        "name": "search_docs",
                                        "arguments": json.dumps({"query": "x"}),
                                    },
                                }
                            ],
                        }
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    return handler


def _budget_task(max_steps_value) -> Task:
    from agent_eval_lab.records.turns import MessageTurn

    return Task(
        id="ws2-budget",
        capability="multi_step_state",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="go"),),
            available_tools=("search_docs",),
        ),
        verification=TrajectorySpec(constraints=()),
        metadata=TaskMetadata(
            split="dev",
            version="2",
            provenance="hand_written",
            max_steps=max_steps_value,
        ),
        initial_state={"docs": {}},
    )


def test_per_task_budget_drives_loop_iterations_over_cli_default() -> None:
    counter = [0]
    handler = _counting_tool_call_handler(counter)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    # CLI default is 4 but the task declares max_steps=6 -> expect 6 iterations.
    run_task_k(
        task=_budget_task(6),
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=1,
        max_steps=4,
        temperature=0.0,
    )
    assert counter[0] == 6


def test_task_without_max_steps_uses_cli_default() -> None:
    counter = [0]
    handler = _counting_tool_call_handler(counter)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    # No declared budget -> falls back to the CLI default of 4.
    run_task_k(
        task=_budget_task(None),
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=1,
        max_steps=4,
        temperature=0.0,
    )
    assert counter[0] == 4


def test_runs_k_times_and_grades_each_run() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_handler))

    results = run_task_k(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=3,
        max_steps=6,
        temperature=0.0,
    )

    assert len(results) == 3
    assert [run.run_index for run in results] == [0, 1, 2]
    assert all(run.task_id == "ws-001" for run in results)
    assert all(run.condition_id == "local:qwen3-8b" for run in results)
    assert all(run.grade.passed for run in results)


def _final_message_handler(request: httpx.Request) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [{"message": {"role": "assistant", "content": "done"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )


def test_run_task_k_precomputes_and_threads_execution_verdicts() -> None:
    """Criterion 13: the oracle edge runs between run_single and grading.

    The model replies immediately, so final_state == initial_state's tree;
    the oracle edge then runs REAL sandboxed pytest over the overlay and the
    pure grader reads its verdict from the threaded map.
    """
    from agent_eval_lab.records.turns import MessageTurn
    from agent_eval_lab.tasks.schema import ExecutionSpec

    task = Task(
        id="cw-001",
        capability="code_repair",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Fix calc.add."),),
            available_tools=(),
        ),
        verification=ExecutionSpec(
            held_out_tests={
                "test_oracle_calc.py": (
                    "from calc import add\n"
                    "\n"
                    "\n"
                    "def test_add():\n"
                    "    assert add(1, 2) == 3\n"
                )
            }
        ),
        metadata=TaskMetadata(split="dev", version="2", provenance="hand_written"),
        initial_state={"files": {"calc.py": "def add(a, b):\n    return a + b\n"}},
    )

    results = run_task_k(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(_final_message_handler)),
        k=1,
        max_steps=2,
        temperature=0.0,
    )

    grade = results[0].grade
    assert grade.grader_id == "execution"
    assert grade.passed is True
    assert grade.evidence["execution"] == "run"
    assert grade.evidence["status"] == "passed"


def test_run_task_k_defaults_yield_byte_identical_workspace_run(monkeypatch) -> None:
    """Criterion 3: the new apply_fn/executor parameters default to today's
    workspace behavior EXACTLY — explicit workspace binding fields serialize
    byte-identically to the defaults. Latency is pinned (monotonic stubbed)
    because wall-clock is the one nondeterministic usage field."""
    import agent_eval_lab.runners.client as client_module
    from agent_eval_lab.records.serialize import run_result_to_dict
    from agent_eval_lab.tools.workspace import apply as workspace_apply

    monkeypatch.setattr(client_module.time, "monotonic", lambda: 0.0)

    def run(**extra):
        return run_task_k(
            task=TASK,
            registry=WORKSPACE_TOOLS,
            config=CONFIG,
            http_client=httpx.Client(transport=httpx.MockTransport(_handler)),
            k=1,
            max_steps=6,
            temperature=0.0,
            **extra,
        )

    defaults = json.dumps(run_result_to_dict(run()[0]), sort_keys=True)
    explicit = json.dumps(
        run_result_to_dict(run(apply_fn=workspace_apply, executor=None)[0]),
        sort_keys=True,
    )
    assert defaults == explicit


def test_run_task_k_threads_code_world_binding_to_run_single() -> None:
    """Criterion 3: a code-world task through run_task_k fulfills run_tests
    via the threaded executor and grades through the oracle edge."""
    from agent_eval_lab.records.turns import MessageTurn, ToolResultTurn, ToolSuccess
    from agent_eval_lab.runners.pytest_edge import execute_request
    from agent_eval_lab.tasks.schema import ExecutionSpec
    from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
    from agent_eval_lab.tools.code_world import apply as code_world_apply

    task = Task(
        id="cw-thread-001",
        capability="code_repair",
        input=TaskInput(
            messages=(MessageTurn(role="user", content="Run the tests."),),
            available_tools=("read_file", "write_file", "list_files", "run_tests"),
        ),
        verification=ExecutionSpec(
            held_out_tests={
                "test_oracle_demo.py": "def test_oracle():\n    assert True\n"
            }
        ),
        metadata=TaskMetadata(split="dev", version="1", provenance="hand_written"),
        initial_state={"files": {"test_demo.py": "def test_ok():\n    assert True\n"}},
    )
    responses = [
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "c1",
                                "type": "function",
                                "function": {"name": "run_tests", "arguments": "{}"},
                            }
                        ],
                    }
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
        {
            "choices": [{"message": {"role": "assistant", "content": "Done."}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    ]
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    [result] = run_task_k(
        task=task,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        k=1,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=execute_request,
    )

    [tool_result] = [
        t for t in result.trajectory.turns if isinstance(t, ToolResultTurn)
    ]
    assert isinstance(tool_result.outcome, ToolSuccess)
    assert tool_result.outcome.result["status"] == "passed"
    assert result.grade.grader_id == "execution"
    assert result.grade.passed is True
    assert result.grade.evidence["execution"] == "run"
