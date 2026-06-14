"""build_b_tasks shape (§4.3). The noskill and skill arms differ ONLY by the
injected stripped-skill system prompt (M2/D25/D37). Golden store + skill fork are
gitignored; the test writes a tmp fake skill file and a tmp fake golden dir so it
is fully deterministic and never reads the real evaluator-only artifacts."""

import json
from pathlib import Path

from agent_eval_lab.datasets.b_tasks import build_b_tasks
from agent_eval_lab.records.turns import MessageTurn
from agent_eval_lab.tasks.schema import ReadbackSpec


def _fake_golden_dir(tmp_path: Path) -> Path:
    d = tmp_path / "b-set-golden"
    d.mkdir()
    (d / "b1-golden.json").write_text(
        json.dumps(
            {
                "exists": True,
                "cube": "Query_CharacteristicValue_Mandatory",
                "rows": ["Years Hierarchy", "Region"],
                "columns": ["Cost"],
                "prompt": "South",
                "grid": [["h"], ["v"]],
            }
        ),
        encoding="utf-8",
    )
    return d


def _fake_skill(tmp_path: Path) -> Path:
    p = tmp_path / "SKILL.md"
    p.write_text("# FAKE stripped strategy-test\nTopic map: ...\n", encoding="utf-8")
    return p


def test_build_b_tasks_returns_the_two_b1_arms(tmp_path: Path) -> None:
    tasks = build_b_tasks(
        golden_dir=_fake_golden_dir(tmp_path),
        strategy_test_path=_fake_skill(tmp_path),
    )
    ids = {t.id for t in tasks}
    assert ids == {"b-b1-noskill", "b-b1-skill"}
    for t in tasks:
        assert t.capability == "browser_mstr"
        assert isinstance(t.verification, ReadbackSpec)
        assert t.metadata.split == "held_out"


def test_skill_arm_carries_the_stripped_skill_noskill_does_not(tmp_path: Path) -> None:
    tasks = {
        t.id: t
        for t in build_b_tasks(
            golden_dir=_fake_golden_dir(tmp_path),
            strategy_test_path=_fake_skill(tmp_path),
        )
    }
    skill_sys = tasks["b-b1-skill"].input.messages[0]
    noskill_sys = tasks["b-b1-noskill"].input.messages[0]
    assert isinstance(skill_sys, MessageTurn) and skill_sys.role == "system"
    assert "FAKE stripped strategy-test" in skill_sys.content
    assert "FAKE stripped strategy-test" not in noskill_sys.content


def test_candidate_prompt_does_not_leak_a_golden_object_id(tmp_path: Path) -> None:
    """TRAP 2: the candidate prompt must stay at problem level — it must never
    contain a golden object id token. (Fake golden uses a placeholder id; this
    asserts the prompt is task-level, not solution-level.)"""
    tasks = build_b_tasks(
        golden_dir=_fake_golden_dir(tmp_path),
        strategy_test_path=_fake_skill(tmp_path),
    )
    for t in tasks:
        user = t.input.messages[-1].content
        # the user turn names the cube/rows/cols/prompt (fair task level) but
        # never an object id or a literal grid value
        assert "object id" not in user.lower()
        assert "golden" not in user.lower()
