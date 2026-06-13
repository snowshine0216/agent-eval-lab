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
        max_tokens=4096,
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


def test_run_task_k_runs_to_safety_cap_when_model_never_finishes() -> None:
    counter = [0]
    handler = _counting_tool_call_handler(counter)
    client = httpx.Client(transport=httpx.MockTransport(handler))
    results = run_task_k(
        task=_budget_task(None),
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=1,
        max_steps=4,  # accepted for CLI back-compat; no longer bounds the loop
        temperature=0.0,
        max_tokens=4096,
    )
    # The model never emits a final message -> the run stops at the 200 cap.
    assert results[0].trajectory.stop_reason == "safety_cap"
    assert results[0].trajectory.safety_cap_bound is True
    assert sum(results[0].trajectory.tool_call_counts.values()) == 200


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
        max_tokens=4096,
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
        max_tokens=4096,
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
            max_tokens=4096,
            **extra,
        )

    defaults = json.dumps(run_result_to_dict(run()[0]), sort_keys=True)
    explicit = json.dumps(
        run_result_to_dict(run(apply_fn=workspace_apply, executor=None)[0]),
        sort_keys=True,
    )
    assert defaults == explicit


def test_run_task_k_threads_run_uid_per_run() -> None:
    client = httpx.Client(transport=httpx.MockTransport(_handler))
    results = run_task_k(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k=3,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    uids = [r.trajectory.run_uid for r in results]
    assert uids == [
        "local:qwen3-8b__0000",
        "local:qwen3-8b__0001",
        "local:qwen3-8b__0002",
    ]


def test_run_task_k_valid_replaces_invalid_until_k_valid() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    # validity_fn: first call invalid, rest valid -> needs one replacement.
    seen = [0]

    def validity_fn(result):
        seen[0] += 1
        return seen[0] != 1  # run #1 invalid, runs #2.. valid

    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=2,
        max_invalid_rate=0.6,
        validity_fn=validity_fn,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 2
    # 3 attempts total (1 invalid + 2 valid); attempt_index increments.
    assert [r.attempt_index for r in outcome.attempts] == [0, 1, 2]


def test_run_task_k_valid_no_void_when_best_case_under_threshold() -> None:
    # Distinguishes the principled best-case VOID predicate from a naive one that
    # ignores already-banked valid runs. k_valid=5, rate=0.40. Sequence by attempt:
    # V V V V  I I I  V  -> 5 valid banked + 3 invalid = 8 trials, final invalid-rate
    # 3/8 = 0.375 <= 0.40, so the condition COMPLETES (void=False). A denominator of
    # (invalid + remaining_needed) would wrongly VOID at the first invalid (4 valid
    # banked, 1 needed -> 1/2 = 0.5 > 0.40); the correct denominator is (invalid +
    # k_valid) -> the minimum achievable final rate (D28/D34).
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    calls = [0]

    def validity_fn(result):
        calls[0] += 1
        return not (5 <= calls[0] <= 7)  # attempts 5,6,7 invalid; rest valid

    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=5,
        max_invalid_rate=0.4,
        validity_fn=validity_fn,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 5
    assert len(outcome.attempts) == 8  # 5 valid + 3 invalid


def test_run_task_k_valid_voids_when_invalid_rate_exceeded() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    client = httpx.Client(transport=httpx.MockTransport(_handler))

    def validity_fn(result):
        return False  # every run invalid

    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=2,
        max_invalid_rate=0.4,
        validity_fn=validity_fn,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is True
    assert len(outcome.valid_runs) < 2  # never scored over fewer than k valid


def test_env_unhealthy_run_counts_as_invalid() -> None:
    from agent_eval_lab.runners.multi_run import run_task_k_valid

    # No validity_fn: invalidity is driven purely by stop_reason == env_unhealthy.
    # Use a health probe that reports post-unhealthy on the first run only.
    flips = [0]

    def probe():
        from agent_eval_lab.records.env_health import EnvHealth

        flips[0] += 1
        # pre always healthy; post unhealthy on the very first post-probe call.
        # Each run calls probe twice (pre, post); the 2nd call is run-1's post.
        post_ok = flips[0] != 2
        return EnvHealth(
            pre_healthy=True, post_healthy=post_ok, pre_status=200,
            post_status=200 if post_ok else 503,
        )

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    outcome = run_task_k_valid(
        task=TASK,
        registry=WORKSPACE_TOOLS,
        config=CONFIG,
        http_client=client,
        k_valid=1,
        max_invalid_rate=0.9,
        health_probe_fn=probe,
        max_steps=6,
        temperature=0.0,
        max_tokens=4096,
    )
    assert outcome.void is False
    assert len(outcome.valid_runs) == 1
    assert any(
        r.run.trajectory.stop_reason == "env_unhealthy" for r in outcome.attempts
    )


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
        max_tokens=4096,
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
