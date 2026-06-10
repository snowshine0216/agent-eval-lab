"""OpenAI-compatible provider client. Pure request/response transforms; the only
effect is the injected transport. Key is read from the env var NAMED by
api_key_env (never hard-coded); tests inject a fake transport (no network).
"""

import json
import os
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from agent_eval_lab.tasks.tool_calls import ToolCall
from agent_eval_lab.tasks.turns import MessageTurn, ToolCallTurn

Transport = Callable[[Mapping[str, Any]], Mapping[str, Any]]


@dataclass(frozen=True, kw_only=True)
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str
    model_id: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    adapter: str | None = None


def build_request(
    config: ProviderConfig,
    *,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Build an OpenAI-compatible /chat/completions request body (pure)."""
    body: dict[str, Any] = {"model": config.model_id, "messages": list(messages)}
    if tools:
        body["tools"] = list(tools)
    return body


def _parse_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    try:
        return dict(json.loads(raw))
    except (ValueError, TypeError):
        return {"__raw__": raw}


def parse_response(
    config: ProviderConfig, payload: Mapping[str, Any]
) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
    """Parse a /chat/completions response into a canonical Turn (pure)."""
    message = payload["choices"][0]["message"]
    usage = dict(payload.get("usage", {}))
    raw_calls = message.get("tool_calls")
    if raw_calls:
        calls = tuple(
            ToolCall(
                call_id=c.get("id", ""),
                name=c["function"]["name"],
                arguments=_parse_arguments(c["function"].get("arguments", {})),
            )
            for c in raw_calls
        )
        return ToolCallTurn(tool_calls=calls, content=message.get("content")), usage
    return MessageTurn(role="assistant", content=message.get("content") or ""), usage


def _real_transport(config: ProviderConfig) -> Transport:  # pragma: no cover - never run in tests
    import urllib.request

    def send(request: Mapping[str, Any]) -> Mapping[str, Any]:
        data = json.dumps(request["body"]).encode("utf-8")
        req = urllib.request.Request(
            f"{config.base_url}/chat/completions", data=data, headers=request["headers"]
        )
        with urllib.request.urlopen(req) as resp:  # noqa: S310
            return json.loads(resp.read().decode("utf-8"))

    return send


class ProviderClient:
    """Thin client: build request, call transport, parse response."""

    def __init__(self, config: ProviderConfig, transport: Transport | None = None) -> None:
        self._config = config
        self._transport = transport if transport is not None else _real_transport(config)

    def _headers(self) -> dict[str, str]:
        key = os.environ.get(self._config.api_key_env, "")
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        return {**headers, **dict(self._config.extra_headers)}

    def complete(
        self,
        *,
        messages: Sequence[Mapping[str, Any]],
        tools: Sequence[Mapping[str, Any]],
    ) -> tuple[MessageTurn | ToolCallTurn, dict[str, int]]:
        body = build_request(self._config, messages=messages, tools=tools)
        payload = self._transport({"body": body, "headers": self._headers()})
        return parse_response(self._config, payload)
