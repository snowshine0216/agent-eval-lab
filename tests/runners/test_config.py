from agent_eval_lab.runners.config import (
    PROVIDERS,
    ProviderConfig,
    condition_id,
    resolve_proxy,
)


def test_registry_covers_the_design_provider_lineup() -> None:
    assert set(PROVIDERS) == {
        "deepseek",
        "dashscope",
        "glm",
        "minimax",
        "openrouter",
        "local",
        "siliconflow",
    }


def test_configs_hold_env_var_names_never_keys() -> None:
    for config in PROVIDERS.values():
        assert config.api_key_env == config.api_key_env.upper()
        assert config.base_url.startswith(("https://", "http://localhost"))


def test_provider_models_and_routes_match_the_refined_lineup() -> None:
    deepseek = PROVIDERS["deepseek"]
    assert deepseek.model_id == "deepseek-v4-pro"
    assert deepseek.base_url == "https://api.deepseek.com"
    assert deepseek.api_key_env == "DEEPSEEK_API_KEY"

    glm = PROVIDERS["glm"]  # GLM is served through SiliconFlow
    assert glm.base_url == "https://api.siliconflow.cn/v1"
    assert glm.model_id == "Pro/zai-org/GLM-5.1"
    assert glm.api_key_env == "SILICONFLOW_API_KEY"

    minimax = PROVIDERS["minimax"]
    assert minimax.base_url == "https://api.minimaxi.com/v1"
    assert minimax.model_id == "MiniMax-M3"
    assert minimax.api_key_env == "MINIMAX_KEY"

    openrouter = PROVIDERS["openrouter"]
    assert openrouter.model_id == "openai/gpt-5.5"
    assert openrouter.api_key_env == "OPENROUTER_API_KEY"


def test_local_provider_needs_no_key() -> None:
    assert PROVIDERS["local"].api_key_env == ""


def test_local_model_id_matches_ollama_served_name() -> None:
    # ollama /v1/models serves the full HF id; a mismatch 404s the chat endpoint
    # (the prior "qwen3-8b" never served inference).
    assert PROVIDERS["local"].model_id == "Qwen/Qwen3-8B"


def test_dashscope_qwen_max_provider_is_wired() -> None:
    ds = PROVIDERS["dashscope"]
    # base_url is the literal compatible-mode path (== DASHSCOPE_BASE_URL value).
    assert ds.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert ds.api_key_env == "DASHSCOPE_API_KEY"  # only the key is read from env
    assert ds.model_id == "qwen3.7-max"
    assert ds.proxy_env is None  # domestic — never proxied


def test_siliconflow_qwen_ladder_provider_is_wired() -> None:
    sf = PROVIDERS["siliconflow"]
    assert sf.base_url == "https://api.siliconflow.cn/v1"
    assert sf.api_key_env == "SILICONFLOW_API_KEY"  # shares the GLM SiliconFlow key
    assert sf.model_id == "Qwen/Qwen3.5-397B-A17B"  # larger ladder rung is the default
    assert sf.proxy_env is None  # domestic — never proxied


def test_condition_id_pairs_provider_and_model() -> None:
    assert condition_id(PROVIDERS["local"]) == "local:Qwen/Qwen3-8B"


def test_extra_headers_default_is_not_shared() -> None:
    first = ProviderConfig(id="a", base_url="https://x", api_key_env="X", model_id="m")
    second = ProviderConfig(id="b", base_url="https://y", api_key_env="Y", model_id="m")

    assert first.extra_headers == {}
    assert first.extra_headers is not second.extra_headers


def test_only_openrouter_opts_into_a_proxy() -> None:
    proxied = {name for name, c in PROVIDERS.items() if c.proxy_env}
    assert proxied == {"openrouter"}
    assert PROVIDERS["openrouter"].proxy_env == "HTTP_PROXY"


def test_resolve_proxy_returns_none_when_provider_does_not_opt_in() -> None:
    # A domestic provider must stay direct even if HTTP_PROXY is set in the env.
    assert resolve_proxy(PROVIDERS["deepseek"], {"HTTP_PROXY": "http://p:8888"}) is None
    assert resolve_proxy(PROVIDERS["local"], {"HTTP_PROXY": "http://p:8888"}) is None


def test_resolve_proxy_reads_the_configured_env_var_for_openrouter() -> None:
    config = PROVIDERS["openrouter"]
    assert resolve_proxy(config, {"HTTP_PROXY": "http://10.0.0.1:8888"}) == (
        "http://10.0.0.1:8888"
    )
    # Opted in but unset/empty -> no proxy (treated as direct, not an error).
    assert resolve_proxy(config, {}) is None
    assert resolve_proxy(config, {"HTTP_PROXY": ""}) is None
