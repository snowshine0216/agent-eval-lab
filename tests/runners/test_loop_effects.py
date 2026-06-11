"""Effect-request fulfillment through the runner loop (ADR-0008)."""

import json

import httpx
import pytest

from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
    TestCaseResult,
    execution_result_to_dict,
)
from agent_eval_lab.records.turns import ToolFailure, ToolResultTurn, ToolSuccess
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.runners.pytest_edge import run_pytest
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply

CONFIG = ProviderConfig(
    id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
)

FILES = {"test_demo.py": "def test_ok():\n    assert True\n"}


def _task(files: dict[str, str]) -> Task:
    return parse_task(
        {
            "id": "cw-loop-001",
            "capability": "code_repair",
            "input": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": "Run the tests.",
                    }
                ],
                "available_tools": [
                    "read_file",
                    "write_file",
                    "list_files",
                    "run_tests",
                ],
            },
            "verification": {
                "type": "output_match",
                "expected_output": "Done.",
            },
            "metadata": {
                "split": "dev",
                "version": "1",
                "provenance": "hand_written",
            },
            "initial_state": {"files": files},
        }
    )


TASK = _task(FILES)

STUB_RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=0,
    failed=1,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_demo::test_ok", status="failed"),),
    stdout="1 failed in <duration>",
    stderr="",
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


def test_loop_fulfills_execution_request_as_tool_success() -> None:
    seen: list[ExecutionRequest] = []

    def executor(request: ExecutionRequest) -> ExecutionResult:
        seen.append(request)
        return STUB_RESULT

    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=executor,
    )

    assert trajectory.stop_reason == "completed"
    result_turn = trajectory.turns[2]
    assert isinstance(result_turn, ToolResultTurn)
    expected = ToolSuccess(result=execution_result_to_dict(STUB_RESULT))
    assert result_turn.outcome == expected
    assert seen == [ExecutionRequest(files=FILES)]
    assert trajectory.final_state == {"files": FILES}


def test_failing_suite_is_still_tool_success() -> None:
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"


def test_fulfillment_matches_request_type_not_tool_name() -> None:
    def request_for_any_tool(*, registry, name, arguments, state):
        return state, ExecutionRequest(files=dict(state.get("files", {})))

    client = _scripted_client(
        [
            _tool_call_response("read_file", {"path": "test_demo.py"}, "c1"),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=request_for_any_tool,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert outcome == ToolSuccess(result=execution_result_to_dict(STUB_RESULT))


def test_execution_request_without_executor_raises_runtime_error() -> None:
    client = _scripted_client([_tool_call_response("run_tests", {}, "c1")])

    with pytest.raises(RuntimeError, match="executor"):
        run_single(
            task=TASK,
            registry=CODE_WORLD_TOOLS,
            config=CONFIG,
            http_client=client,
            run_index=0,
            max_steps=4,
            temperature=0.0,
            apply_fn=code_world_apply,
        )


def test_pure_validation_still_fails_as_tool_failure() -> None:
    client = _scripted_client(
        [
            _tool_call_response("read_file", {"path": "../etc/passwd"}, "c1"),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolFailure)


def test_executor_exception_propagates_out_of_run_single() -> None:
    """An executor that raises must not be swallowed — it propagates to caller."""
    client = _scripted_client([_tool_call_response("run_tests", {}, "c1")])

    def boom(request: ExecutionRequest) -> ExecutionResult:
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        run_single(
            task=TASK,
            registry=CODE_WORLD_TOOLS,
            config=CONFIG,
            http_client=client,
            run_index=0,
            max_steps=4,
            temperature=0.0,
            apply_fn=code_world_apply,
            executor=boom,
        )


def test_loop_with_real_edge_records_failed_suite() -> None:
    failing = {"test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=_task(failing),
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: run_pytest(request.files, timeout_s=30.0),
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"
    assert outcome.result["failed"] == 1
    assert outcome.result["tests"] == [
        {"test_id": "test_bug::test_bug", "status": "failed"}
    ]
    assert "<duration>" in outcome.result["stdout"]


def test_execute_request_fulfills_run_tests_through_the_loop() -> None:
    """Criterion 2: the shipped pytest-edge executor, end to end through
    run_single — a fulfilled run_tests records ToolSuccess carrying a
    serialized ExecutionResult, whatever the suite status (ADR-0008)."""
    from agent_eval_lab.runners.pytest_edge import execute_request

    failing = {"test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=_task(failing),
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=execute_request,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"
    assert outcome.result["exit_code"] == 1
    assert "<sandbox>" in outcome.result["stdout"] or outcome.result["stdout"]
