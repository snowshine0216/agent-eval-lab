"""Tests for experiments/evaluator_config.py — TOML loader."""

from pathlib import Path

import pytest

from agent_eval_lab.experiments.evaluator_config import (
    EvaluatorConfig,
    HealthProbeConfig,
    OracleBSetConfig,
    RunnerConfig,
    SkillConfig,
    StoreConfig,
    load_evaluator_config,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_evaluator_config_returns_typed_config() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg, EvaluatorConfig)


def test_load_evaluator_config_store() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg.store, StoreConfig)
    assert cfg.store.path == "/tmp/eval-store"


def test_load_evaluator_config_health_probe() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg.health_probe, HealthProbeConfig)
    assert cfg.health_probe.url == "http://mstr.example.com/api/auth/login"
    assert cfg.health_probe.username == "evaluator"
    assert cfg.health_probe.password == "s3cr3t!"  # verbatim


def test_load_evaluator_config_skill() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg.skill, SkillConfig)
    assert cfg.skill.strategy_test_path == "/tmp/strategy_test.js"


def test_load_evaluator_config_runner() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg.runner, RunnerConfig)
    assert cfg.runner.safety_cap == 12
    assert cfg.runner.k_valid == 3
    assert cfg.runner.max_invalid_rate == 0.25


def test_load_evaluator_config_oracle_b_set() -> None:
    # §18.4: nested [oracle.b_set] section; readback is a strategy STRING.
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    assert isinstance(cfg.oracle_b_set, OracleBSetConfig)
    assert cfg.oracle_b_set.readback == "playwright-cli"


def test_load_evaluator_config_oracle_section_must_be_nested() -> None:
    """A flat [oracle_b_set] (not §18.4's nested [oracle.b_set]) must be rejected."""
    bad = (FIXTURES.parent / "_bad_oracle.toml")
    base = (FIXTURES / "evaluator.toml").read_text().replace(
        "[oracle.b_set]", "[oracle_b_set]"
    )
    bad.write_text(base)
    try:
        with pytest.raises(ValueError, match=r"\[oracle"):
            load_evaluator_config(bad)
    finally:
        bad.unlink()


def test_load_evaluator_config_frozen() -> None:
    cfg = load_evaluator_config(FIXTURES / "evaluator.toml")
    with pytest.raises(Exception):
        cfg.store = cfg.store  # type: ignore[misc]


def test_load_evaluator_config_missing_section_raises(tmp_path: Path) -> None:
    """Missing required section must raise a clear error."""
    toml_path = tmp_path / "bad.toml"
    toml_path.write_text("[store]\npath = '/tmp/x'\n")
    with pytest.raises((KeyError, ValueError)):
        load_evaluator_config(toml_path)


def test_load_evaluator_config_file_not_found_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_evaluator_config(Path("/nonexistent/path/evaluator.toml"))
