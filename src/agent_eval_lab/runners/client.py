"""EDGE: OpenAI-compatible /chat/completions client with retry and latency."""

import os
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import httpx

from agent_eval_lab.runners.config import ProviderConfig

_RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


@dataclass(frozen=True, kw_only=True)
class ProviderResponse:
    payload: Mapping[str, Any]
    latency_s: float


def _headers(config: ProviderConfig) -> dict[str, str]:
    headers = dict(config.extra_headers)
    if config.api_key_env:
        key = os.environ.get(config.api_key_env)
        if not key:
            raise RuntimeError(f"missing environment variable: {config.api_key_env}")
        headers["Authorization"] = f"Bearer {key}"
    return headers


def chat_completion(
    *,
    config: ProviderConfig,
    messages: Sequence[Mapping[str, Any]],
    tools: Sequence[Mapping[str, Any]],
    temperature: float,
    http_client: httpx.Client,
    max_attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> ProviderResponse:
    """POST /chat/completions. latency_s covers only the successful attempt;
    retry backoff is deliberately excluded (provider latency, not harness policy).
    """
    headers = _headers(config)
    body: dict[str, Any] = {
        "model": config.model_id,
        "messages": list(messages),
        "temperature": temperature,
    }
    if tools:
        body["tools"] = list(tools)
    url = f"{config.base_url}/chat/completions"
    for attempt in range(1, max_attempts + 1):
        start = time.monotonic()
        try:
            response = http_client.post(url, json=body, headers=headers)
        except httpx.TransportError:
            if attempt == max_attempts:
                raise
            sleep(float(attempt))
            continue
        if response.status_code in _RETRYABLE_STATUS and attempt < max_attempts:
            sleep(float(attempt))
            continue
        response.raise_for_status()
        return ProviderResponse(
            payload=response.json(), latency_s=time.monotonic() - start
        )
    raise RuntimeError("unreachable: retry loop exited without return or raise")
