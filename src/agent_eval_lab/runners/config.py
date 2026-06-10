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


PROVIDERS: Mapping[str, ProviderConfig] = {
    "deepseek": ProviderConfig(
        id="deepseek",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_id="deepseek-v4",
    ),
    "glm": ProviderConfig(
        id="glm",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        api_key_env="ZHIPU_API_KEY",
        model_id="glm-5",
    ),
    "minimax": ProviderConfig(
        id="minimax",
        base_url="https://api.minimax.io/v1",
        api_key_env="MINIMAX_API_KEY",
        model_id="minimax-m2.1",
    ),
    "qwen": ProviderConfig(
        id="qwen",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key_env="DASHSCOPE_API_KEY",
        model_id="qwen3-max",
    ),
    "openrouter": ProviderConfig(
        id="openrouter",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        model_id="anthropic/claude-sonnet-4-6",
    ),
    "local": ProviderConfig(
        id="local",
        base_url="http://localhost:11434/v1",
        api_key_env="",
        model_id="qwen3-8b",
    ),
}
