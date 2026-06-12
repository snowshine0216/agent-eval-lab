import httpx
import pytest

from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig

CONFIG = ProviderConfig(
    id="test",
    base_url="https://api.test.example",
    api_key_env="TEST_API_KEY",
    model_id="test-model",
)
OK_PAYLOAD = {
    "choices": [{"message": {"role": "assistant", "content": "Done."}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5},
}


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_sends_bearer_key_from_env_and_returns_payload(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        seen["url"] = str(request.url)
        return httpx.Response(200, json=OK_PAYLOAD)

    response = chat_completion(
        config=CONFIG,
        messages=({"role": "user", "content": "hi"},),
        tools=(),
        temperature=0.0,
        max_tokens=4096,
        http_client=_client(handler),
    )

    assert seen["auth"] == "Bearer sk-test"
    assert seen["url"] == "https://api.test.example/chat/completions"
    assert response.payload == OK_PAYLOAD
    assert response.latency_s >= 0.0


def test_missing_key_env_raises(monkeypatch) -> None:
    monkeypatch.delenv("TEST_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="TEST_API_KEY"):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            max_tokens=4096,
            http_client=_client(lambda request: httpx.Response(200, json=OK_PAYLOAD)),
        )


def test_empty_api_key_env_skips_auth_header() -> None:
    local = ProviderConfig(
        id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
    )
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=OK_PAYLOAD)

    chat_completion(
        config=local,
        messages=(),
        tools=(),
        temperature=0.0,
        max_tokens=4096,
        http_client=_client(handler),
    )

    assert seen["auth"] is None


def test_retries_on_server_error_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=OK_PAYLOAD)

    response = chat_completion(
        config=CONFIG,
        messages=(),
        tools=(),
        temperature=0.0,
        max_tokens=4096,
        http_client=_client(handler),
        sleep=lambda seconds: None,
    )

    assert attempts["n"] == 3
    assert response.payload == OK_PAYLOAD


def test_retries_on_transport_error_then_succeeds(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    attempts = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise httpx.ConnectError("boom", request=request)
        return httpx.Response(200, json=OK_PAYLOAD)

    response = chat_completion(
        config=CONFIG,
        messages=(),
        tools=(),
        temperature=0.0,
        max_tokens=4096,
        http_client=_client(handler),
        sleep=lambda seconds: None,
    )

    assert attempts["n"] == 2
    assert response.payload == OK_PAYLOAD


def test_exhausted_transport_errors_raise(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(httpx.ConnectError):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            max_tokens=4096,
            http_client=_client(handler),
            sleep=lambda seconds: None,
        )


def test_exhausted_retries_raise(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")

    with pytest.raises(httpx.HTTPStatusError):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            max_tokens=4096,
            http_client=_client(lambda request: httpx.Response(429, json={})),
            sleep=lambda seconds: None,
        )


def test_tools_are_included_only_when_present(monkeypatch) -> None:
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        bodies.append(_json.loads(request.content))
        return httpx.Response(200, json=OK_PAYLOAD)

    client = _client(handler)
    chat_completion(
        config=CONFIG,
        messages=(),
        tools=(),
        temperature=0.5,
        max_tokens=4096,
        http_client=client,
    )
    chat_completion(
        config=CONFIG,
        messages=(),
        tools=({"type": "function", "function": {"name": "x"}},),
        temperature=0.5,
        max_tokens=4096,
        http_client=client,
    )

    assert "tools" not in bodies[0]
    assert bodies[1]["tools"] == [{"type": "function", "function": {"name": "x"}}]
    assert bodies[1]["model"] == "test-model"
    assert bodies[1]["temperature"] == 0.5


def test_max_tokens_is_always_present_in_request_body(monkeypatch) -> None:
    """The completion budget is an explicit eval parameter, never a provider default.

    Every request must carry max_tokens regardless of whether tools are present,
    to prevent provider-side defaults from silently truncating thinking-model
    reasoning budgets (item 004 harness defect: 27/45 local runs truncated at
    the MLX server's 512-token default).
    """
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        bodies.append(_json.loads(request.content))
        return httpx.Response(200, json=OK_PAYLOAD)

    client = _client(handler)
    chat_completion(
        config=CONFIG,
        messages=({"role": "user", "content": "hi"},),
        tools=(),
        temperature=0.0,
        max_tokens=4096,
        http_client=client,
    )

    assert bodies[0]["max_tokens"] == 4096


def test_max_tokens_value_threads_through_to_request(monkeypatch) -> None:
    """Different max_tokens values survive the round-trip to the wire."""
    monkeypatch.setenv("TEST_API_KEY", "sk-test")
    bodies: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json

        bodies.append(_json.loads(request.content))
        return httpx.Response(200, json=OK_PAYLOAD)

    client = _client(handler)
    for max_tokens in (512, 2048, 8192):
        chat_completion(
            config=CONFIG,
            messages=(),
            tools=(),
            temperature=0.0,
            max_tokens=max_tokens,
            http_client=client,
        )

    assert [b["max_tokens"] for b in bodies] == [512, 2048, 8192]
