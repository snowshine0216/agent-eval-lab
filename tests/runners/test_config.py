from agent_eval_lab.runners.config import PROVIDERS, ProviderConfig


def test_registry_covers_the_design_provider_lineup() -> None:
    assert set(PROVIDERS) == {
        "deepseek",
        "glm",
        "minimax",
        "qwen",
        "openrouter",
        "local",
    }


def test_configs_hold_env_var_names_never_keys() -> None:
    for config in PROVIDERS.values():
        assert config.api_key_env == config.api_key_env.upper()
        assert config.base_url.startswith(("https://", "http://localhost"))


def test_local_provider_needs_no_key() -> None:
    assert PROVIDERS["local"].api_key_env == ""


def test_extra_headers_default_is_not_shared() -> None:
    first = ProviderConfig(id="a", base_url="https://x", api_key_env="X", model_id="m")
    second = ProviderConfig(id="b", base_url="https://y", api_key_env="Y", model_id="m")

    assert first.extra_headers == {}
    assert first.extra_headers is not second.extra_headers
