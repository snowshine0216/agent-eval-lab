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
            messages=(
                MessageTurn(role="user", content="go"),
            ),
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
    client = httpx.Client(transport=httpx.MockTransport(_counting_tool_call_handler(counter)))
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
    client = httpx.Client(transport=httpx.MockTransport(_counting_tool_call_handler(counter)))
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
