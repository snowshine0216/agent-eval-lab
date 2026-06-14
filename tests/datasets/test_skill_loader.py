"""The stripped-skill loader reads SKILL.md text (§18.9/D27). Test against a
tmp fixture file the test writes — NEVER the real gitignored evaluator-only fork."""

from pathlib import Path

import pytest

from agent_eval_lab.datasets.skill_loader import load_stripped_skill


def test_load_stripped_skill_returns_the_file_text(tmp_path: Path) -> None:
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "# FAKE stripped strategy-test\nTopic map: ...\n", encoding="utf-8"
    )
    text = load_stripped_skill(skill)
    assert "FAKE stripped strategy-test" in text


def test_load_stripped_skill_raises_clear_error_when_absent(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_stripped_skill(tmp_path / "missing" / "SKILL.md")
