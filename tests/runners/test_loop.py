import json

import httpx

from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

CONFIG = ProviderConfig(
    id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
)

TASK = parse_task(
    {
        "id": "ws-017",
        "capability": "multi_step",
        "input": {
            "messages": [
                {"type": "message", "role": "user", "content": "Create then close."}
            ],
            "available_tools": ["search_docs", "create_ticket", "update_ticket"],
        },
        "verification": {
            "type": "tool_call_match",
            "expected_tool_calls": [
                {
                    "name": "create_ticket",
                    "arguments": {"title": "x", "priority": "low"},
                },
                {
                    "name": "update_ticket",
                    "arguments": {"ticket_id": "T-1", "status": "closed"},
                },
            ],
            "match": "exact_sequence",
        },
        "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
        "initial_state": {"docs": {}, "tickets": {}},
    }
)


def _tool_call_response(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


def _final_response(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 5},
    }


def _scripted_client(responses: list[dict]) -> httpx.Client:
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_loop_threads_state_and_stops_on_final_message() -> None:
    client = _scripted_client(
        [
            _tool_call_response(
                "create_ticket", {"title": "x", "priority": "low"}, "c1"
            ),
            _tool_call_response(
                "update_ticket", {"ticket_id": "T-1", "status": "closed"}, "c2"
            ),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=6,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "completed"
    kinds = [type(turn) for turn in trajectory.turns]
    assert kinds == [
        MessageTurn,  # user
        ToolCallTurn,  # create
        ToolResultTurn,
        ToolCallTurn,  # update
        ToolResultTurn,
        MessageTurn,  # final assistant
    ]
    create_result = trajectory.turns[2]
    assert isinstance(create_result.outcome, ToolSuccess)
    assert create_result.outcome.result == {"ticket_id": "T-1"}
    update_result = trajectory.turns[4]
    assert update_result.outcome.result == {"ticket_id": "T-1", "status": "closed"}
    assert trajectory.usage.prompt_tokens == 70
    assert trajectory.usage.completion_tokens == 25
    assert trajectory.run_index == 0


def test_loop_records_parse_failure_and_stops() -> None:
    bad = {
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
                                "name": "search_docs",
                                "arguments": '{"query": ',
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    client = _scripted_client([bad])

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=1,
        max_steps=6,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "parse_failure"
    assert trajectory.parse_failure is not None
    assert trajectory.run_index == 1


def test_loop_enforces_max_steps() -> None:
    responses = [
        _tool_call_response("search_docs", {"query": "x"}, f"c{i}") for i in range(5)
    ]
    client = _scripted_client(responses)

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=2,
        temperature=0.0,
    )

    assert trajectory.stop_reason == "max_steps"
    tool_call_turns = [t for t in trajectory.turns if isinstance(t, ToolCallTurn)]
    assert len(tool_call_turns) == 2
