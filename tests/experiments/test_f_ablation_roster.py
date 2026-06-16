"""Tests for the config-driven F-ablation roster loader (the version-controlled
source of truth for WHICH models the ablation compares)."""

from pathlib import Path

import pytest

from agent_eval_lab.experiments.f_ablation_roster import (
    FAblationRoster,
    load_f_ablation_roster,
)

# The committed default roster lives at repo root (parity with evaluator.toml).
_DEFAULT_ROSTER = Path(__file__).resolve().parents[2] / "f-ablation-roster.toml"


def test_committed_default_is_the_three_model_v3_roster():
    roster = load_f_ablation_roster(_DEFAULT_ROSTER)
    assert isinstance(roster, FAblationRoster)
    assert roster.experiment_id == "F-ablation-v3"
    assert [c.condition_id for c in roster.conditions] == [
        "deepseek:deepseek-v4-pro",
        "minimax:MiniMax-M3",
        "dashscope:qwen3.7-max",
    ]
    # GLM is no longer in the roster; v3 swapped the SiliconFlow Qwen rung for
    # DashScope's qwen3.7-max, so neither legacy provider is referenced.
    assert all("glm" not in c.condition_id for c in roster.conditions)
    assert all("siliconflow" not in c.condition_id for c in roster.conditions)
    # the Qwen rung is now the DashScope flagship.
    qwen = next(c for c in roster.conditions if c.condition_id.startswith("dashscope"))
    assert qwen.label == "qwen3.7-max (dashscope)"


def _write(tmp_path: Path, body: str) -> Path:
    p = tmp_path / "roster.toml"
    p.write_text(body, encoding="utf-8")
    return p


def test_entry_order_is_preserved(tmp_path):
    roster = load_f_ablation_roster(
        _write(
            tmp_path,
            'experiment_id = "x"\n'
            '[[model]]\ncondition_id = "minimax:MiniMax-M3"\nlabel = "m"\n'
            '[[model]]\ncondition_id = "deepseek:deepseek-v4-pro"\nlabel = "d"\n',
        )
    )
    assert [c.condition_id for c in roster.conditions] == [
        "minimax:MiniMax-M3",
        "deepseek:deepseek-v4-pro",
    ]


def test_missing_experiment_id_is_a_clear_error(tmp_path):
    body = '[[model]]\ncondition_id = "deepseek:deepseek-v4-pro"\nlabel = "d"\n'
    with pytest.raises(ValueError, match="experiment_id"):
        load_f_ablation_roster(_write(tmp_path, body))


def test_empty_roster_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="at least one"):
        load_f_ablation_roster(_write(tmp_path, 'experiment_id = "x"\n'))


def test_condition_id_must_be_provider_colon_model(tmp_path):
    body = 'experiment_id = "x"\n[[model]]\ncondition_id = "deepseek"\nlabel = "d"\n'
    with pytest.raises(ValueError, match="provider:model"):
        load_f_ablation_roster(_write(tmp_path, body))


def test_unknown_provider_is_rejected_before_any_run(tmp_path):
    body = (
        'experiment_id = "x"\n'
        '[[model]]\ncondition_id = "nope:some-model"\nlabel = "n"\n'
    )
    with pytest.raises(ValueError, match="unknown provider"):
        load_f_ablation_roster(
            _write(tmp_path, body),
            valid_providers=frozenset({"deepseek", "minimax", "siliconflow"}),
        )


def test_model_entry_missing_label_is_a_clear_error(tmp_path):
    body = 'experiment_id = "x"\n[[model]]\ncondition_id = "deepseek:deepseek-v4-pro"\n'
    with pytest.raises(ValueError, match="label"):
        load_f_ablation_roster(_write(tmp_path, body))
