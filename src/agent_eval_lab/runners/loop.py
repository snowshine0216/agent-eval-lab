"""EDGE: the model<->tool loop. Holds state, threads it through pure `apply`."""

import json
from collections.abc import Mapping

import httpx

from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import MessageTurn, ToolResultTurn, Turn
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.parse import parse_assistant_payload
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef, apply


def run_single(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    max_steps: int,
    temperature: float,
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
                error="no choices in provider response",
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
            state, outcome = apply(
                registry=registry, name=call.name, arguments=call.arguments, state=state
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
    )
