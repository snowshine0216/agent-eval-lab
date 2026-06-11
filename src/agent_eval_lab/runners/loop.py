"""EDGE: the model<->tool loop. Holds state, threads it through pure `apply`.

Effect-requests (ADR-0008): when a world's apply returns an ExecutionRequest
in the outcome position, the loop fulfills it through the executor callable —
matched on the request type, never the tool-name string — and records the
fulfilled ToolSuccess (serialized ExecutionResult) on the trajectory. A
fulfilled request is always ToolSuccess, whatever the suite status;
ToolFailure stays reserved for pure validation.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
    execution_result_to_dict,
)
from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    ParseFailure,
    Trajectory,
    Usage,
)
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolOutcome,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.parse import parse_assistant_payload
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef, apply

ApplyFn = Callable[..., tuple[Mapping[str, Any], ToolOutcome | ExecutionRequest]]
Executor = Callable[[ExecutionRequest], ExecutionResult]


def _fulfill(request: ExecutionRequest, executor: Executor | None) -> ToolSuccess:
    """Fulfill an effect-request at the edge; always ToolSuccess (ADR-0008)."""
    if executor is None:
        raise RuntimeError(
            "harness misconfiguration: apply returned an ExecutionRequest but "
            "no executor is configured"
        )
    return ToolSuccess(result=execution_result_to_dict(executor(request)))


def run_single(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn = apply,
    executor: Executor | None = None,
) -> Trajectory:
    state = dict(task.initial_state or {})
    turns: list[Turn] = list(task.input.messages)
    missing = tuple(n for n in task.input.available_tools if n not in registry)
    if missing:
        raise ValueError(f"tools not in registry: {missing}")
    tools = tuple(
        tooldef_to_openai(registry[name]) for name in task.input.available_tools
    )
    prompt_tokens = 0
    completion_tokens = 0
    latency_s = 0.0
    parse_failure: ParseFailure | None = None
    stop_reason = "max_steps"

    for _ in range(max_steps):
        response = chat_completion(
            config=config,
            messages=tuple(turn_to_message(turn) for turn in turns),
            tools=tools,
            temperature=temperature,
            max_tokens=max_tokens,
            http_client=http_client,
        )
        usage = response.payload.get("usage", {})
        prompt_tokens += usage.get("prompt_tokens", 0)
        completion_tokens += usage.get("completion_tokens", 0)
        latency_s += response.latency_s
        choices = response.payload.get("choices") or []
        if not choices:
            parse_failure = ParseFailure(
                raw=json.dumps(dict(response.payload)),
                error=NO_CHOICES_ERROR,
            )
            stop_reason = "parse_failure"
            break
        parsed = parse_assistant_payload(choices[0].get("message", {}))
        if isinstance(parsed, ParseFailure):
            parse_failure = parsed
            stop_reason = "parse_failure"
            break
        turns.append(parsed)
        if isinstance(parsed, MessageTurn):
            stop_reason = "completed"
            break
        for call in parsed.tool_calls:
            state, applied = apply_fn(
                registry=registry,
                name=call.name,
                arguments=call.arguments,
                state=state,
            )
            outcome = (
                _fulfill(applied, executor)
                if isinstance(applied, ExecutionRequest)
                else applied
            )
            turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))

    return Trajectory(
        turns=tuple(turns),
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency_s,
        ),
        run_index=run_index,
        stop_reason=stop_reason,
        parse_failure=parse_failure,
        final_state=state,
        max_tokens=max_tokens,
    )
