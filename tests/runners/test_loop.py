import json

import httpx
import pytest

from agent_eval_lab.records.env_health import EnvHealth
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
        temperature=0.0,
        max_tokens=4096,
    )

    assert trajectory.stop_reason == "completed_natural"
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
        temperature=0.0,
        max_tokens=4096,
    )

    assert trajectory.stop_reason == "parse_failure"
    assert trajectory.parse_failure is not None
    assert trajectory.run_index == 1


def test_loop_records_missing_choices_as_parse_failure() -> None:
    client = _scripted_client(
        [{"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}]
    )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )

    assert trajectory.stop_reason == "parse_failure"
    assert trajectory.parse_failure is not None
    assert "no choices" in trajectory.parse_failure.error


def test_run_single_records_final_state() -> None:
    client = _scripted_client(
        [
            _tool_call_response(
                "create_ticket", {"title": "Broken login", "priority": "high"}, "c1"
            ),
            _final_response("Created the ticket."),
        ]
    )
    task = parse_task(
        {
            "id": "ws-final-state",
            "capability": "tool_selection",
            "input": {
                "messages": [
                    {"type": "message", "role": "user", "content": "Create a ticket."}
                ],
                "available_tools": ["create_ticket"],
            },
            "verification": {
                "type": "output_match",
                "expected_output": "Created the ticket.",
            },
            "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
            "initial_state": {"tickets": {}},
        }
    )

    trajectory = run_single(
        task=task,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )

    assert trajectory.final_state is not None
    assert trajectory.final_state["tickets"]["T-1"]["title"] == "Broken login"


def test_loop_rejects_task_referencing_unregistered_tool() -> None:
    task = parse_task(
        {
            "id": "ws-bad",
            "capability": "tool_selection",
            "input": {
                "messages": [{"type": "message", "role": "user", "content": "hi"}],
                "available_tools": ["search_docs", "nonexistent"],
            },
            "verification": {
                "type": "tool_call_match",
                "expected_tool_calls": [
                    {"name": "search_docs", "arguments": {"query": "x"}}
                ],
                "match": "exact_sequence",
            },
            "metadata": {"split": "dev", "version": "1", "provenance": "hand_written"},
            "initial_state": {"docs": {}, "tickets": {}},
        }
    )
    client = _scripted_client([_final_response("Done.")])

    with pytest.raises(ValueError, match="not in registry"):
        run_single(
            task=task,
            registry=WORKSPACE_TOOLS,
            config=CONFIG,
            http_client=client,
            run_index=0,
            temperature=0.0,
            max_tokens=4096,
        )


def test_empty_choices_records_the_shared_constant_verbatim() -> None:
    """Grill Q3: the classifier's harness/agent parse split keys on this exact
    string; loop and classifier share one constant so the split cannot drift."""
    from agent_eval_lab.records.trajectory import NO_CHOICES_ERROR

    client = _scripted_client(
        [{"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}]
    )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )

    assert trajectory.parse_failure is not None
    assert trajectory.parse_failure.error == NO_CHOICES_ERROR


def test_run_single_sends_max_tokens_in_every_request() -> None:
    """The completion budget is an explicit eval parameter (item 004 fix 1).

    run_single must thread max_tokens into every chat_completion call so the
    request body always carries max_tokens — never a provider default.
    """
    import json as _json

    seen_bodies: list[dict] = []

    def capturing_handler(request: httpx.Request) -> httpx.Response:
        seen_bodies.append(_json.loads(request.content))
        # Return a final-message response to end the loop after one turn
        return httpx.Response(
            200,
            json=_final_response("Done."),
        )

    client = httpx.Client(transport=httpx.MockTransport(capturing_handler))
    run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )

    assert all("max_tokens" in body for body in seen_bodies), (
        "every request must carry max_tokens; none must rely on provider defaults"
    )
    assert all(body["max_tokens"] == 4096 for body in seen_bodies)


def test_run_single_records_max_tokens_on_trajectory() -> None:
    """Trajectory carries max_tokens so the classifier can derive
    token_budget_exhausted from the artifact without re-parsing CLI args."""
    client = _scripted_client([_final_response("Done.")])
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=2048,
    )
    assert trajectory.max_tokens == 2048


# --- Task 4 new tests: natural completion, rounds/counts, run_uid, wall_time ---


def test_loop_completes_naturally_emits_completed_natural() -> None:
    client = _scripted_client(
        [
            _tool_call_response("search_docs", {"query": "x"}, "c1"),
            _final_response("Done."),
        ]
    )
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.stop_reason == "completed_natural"
    assert trajectory.safety_cap_bound is False


def test_loop_counts_rounds_and_per_tool_calls() -> None:
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
        temperature=0.0,
        max_tokens=4096,
    )
    # 3 model turns: two tool-call turns + one final message.
    assert trajectory.rounds == 3
    assert trajectory.tool_call_counts == {"create_ticket": 1, "update_ticket": 1}


def test_loop_threads_run_uid() -> None:
    client = _scripted_client([_final_response("Done.")])
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=3,
        temperature=0.0,
        max_tokens=4096,
        run_uid="local:m__0003",
    )
    assert trajectory.run_uid == "local:m__0003"


def test_loop_records_wall_time_from_latency() -> None:
    client = _scripted_client([_final_response("Done.")])
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    # wall_time_s mirrors accumulated provider latency (usage.latency_s).
    assert trajectory.wall_time_s == trajectory.usage.latency_s


# --- Task 5 new tests: safety cap + health probe ---


def _always_tool_call_client():
    """A client that always returns a fresh tool call (never a final message),
    so the loop only stops at the safety cap."""
    counter = [0]

    def handler(request):
        counter[0] += 1
        return httpx.Response(
            200,
            json=_tool_call_response("search_docs", {"query": "x"}, f"c{counter[0]}"),
        )

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_loop_stops_at_safety_cap() -> None:
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_always_tool_call_client(),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        safety_cap=3,  # small cap so the test is fast; production default is 200
    )
    assert trajectory.stop_reason == "safety_cap"
    assert trajectory.safety_cap_bound is True
    # Exactly the cap's worth of tool calls were recorded (one tool call per turn).
    assert sum(trajectory.tool_call_counts.values()) == 3


def test_safety_cap_default_is_200() -> None:
    import inspect

    sig = inspect.signature(run_single)
    assert sig.parameters["safety_cap"].default == 200


def test_health_probe_called_pre_and_post_records_env_health() -> None:
    calls = []

    def probe():
        calls.append("probe")
        # pre healthy, the test inspects only that it was recorded twice
        return EnvHealth(
            pre_healthy=True, post_healthy=True, pre_status=200, post_status=200
        )

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=probe,
    )
    assert len(calls) == 2  # pre + post
    assert trajectory.env_health is not None
    assert trajectory.env_health.pre_healthy is True
    assert trajectory.env_health.post_healthy is True
    # A healthy post-probe does not override a natural completion.
    assert trajectory.stop_reason == "completed_natural"


def test_post_probe_unhealthy_sets_env_unhealthy_stop_reason() -> None:
    results = iter(
        [
            EnvHealth(  # pre
                pre_healthy=True, post_healthy=True, pre_status=200, post_status=200
            ),
            EnvHealth(  # post
                pre_healthy=True, post_healthy=False, pre_status=200, post_status=503
            ),
        ]
    )

    def probe():
        return next(results)

    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
        health_probe_fn=probe,
    )
    assert trajectory.stop_reason == "env_unhealthy"
    assert trajectory.env_health is not None
    assert trajectory.env_health.post_healthy is False
    assert trajectory.env_health.pre_healthy is True


def test_no_health_probe_yields_none_env_health() -> None:
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=_scripted_client([_final_response("Done.")]),
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.env_health is None
    assert trajectory.stop_reason == "completed_natural"


# --- item 008: per-run provider errors are recorded, not crashes ---


def test_loop_records_provider_http_error_as_parse_failure() -> None:
    """A non-retryable provider error (e.g. the SiliconFlow 400 from context length
    that aborted a GLM-5.1 D-run) is recorded as a failed run, never raised — one
    bad request can no longer abort and lose a whole model's multi-task run."""
    from agent_eval_lab.records.trajectory import PROVIDER_ERROR

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400, json={"error": {"message": "maximum context length exceeded"}}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    trajectory = run_single(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        temperature=0.0,
        max_tokens=4096,
    )
    assert trajectory.stop_reason == "parse_failure"
    assert trajectory.parse_failure is not None
    assert trajectory.parse_failure.error == PROVIDER_ERROR
    assert "400" in trajectory.parse_failure.raw
    assert "context length" in trajectory.parse_failure.raw


def test_provider_error_raw_carries_no_auth_header() -> None:
    """The recorded detail is the response body + status only — the API key lives in
    request headers, never the response, so nothing sensitive is captured."""
    from agent_eval_lab.runners.loop import _provider_error_raw

    request = httpx.Request(
        "POST", "https://x/chat/completions", headers={"Authorization": "Bearer SECRET"}
    )
    response = httpx.Response(429, text="rate limited", request=request)
    exc = httpx.HTTPStatusError("429", request=request, response=response)
    raw = _provider_error_raw(exc)
    assert "SECRET" not in raw
    assert "429" in raw and "rate limited" in raw
