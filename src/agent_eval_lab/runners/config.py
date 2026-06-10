"""Provider configuration (spec §3): one OpenAI-compatible client, many configs."""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True, kw_only=True)
class ProviderConfig:
    id: str
    base_url: str
    api_key_env: str  # env var NAME holding the dedicated key (never the key)
    model_id: str
    extra_headers: Mapping[str, str] = field(default_factory=dict)
    adapter: str | None = None  # reserved: pure tool-call dialect normalizer
    proxy_env: str | None = None  # env var NAME holding the proxy URL; opt-in


def condition_id(config: ProviderConfig) -> str:
    """Stable identifier pairing provider and model for run/report records."""
    return f"{config.id}:{config.model_id}"


def resolve_proxy(config: ProviderConfig, env: Mapping[str, str]) -> str | None:
    """Proxy URL for this provider, or None.

    Proxying is opt-in per provider (only those with ``proxy_env`` set) and the
    URL is read from that named env var, so it stays configurable. A provider
    that opts in but whose env var is unset/empty is treated as direct, not an
    error — domestic providers and ``localhost`` are never proxied.
    """
    if not config.proxy_env:
        return None
    return env.get(config.proxy_env) or None


PROVIDERS: Mapping[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        id="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_id="deepseek-v4-pro",
    ),
    "glm": ProviderConfig(
        id="glm",  # GLM is served through SiliconFlow's OpenAI-compatible API
        base_url="https://api.siliconflow.cn/v1",
        api_key_env="SILICONFLOW_API_KEY",
        model_id="Pro/zai-org/GLM-5.1",
    ),
    "minimax": ProviderConfig(
        id="minimax",
        base_url="https://api.minimaxi.com/v1",
        api_key_env="MINIMAX_KEY",  # the working key is named MINIMAX_KEY in .env
        model_id="MiniMax-M3",
    ),
    "openrouter": ProviderConfig(
        id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        model_id="openai/gpt-5.5",
        proxy_env="HTTP_PROXY",  # reached through the corporate proxy
    ),
    "local": ProviderConfig(
        id="local",
        base_url="http://localhost:11434/v1",
        api_key_env="",
        model_id="qwen3-8b",
    ),
}
