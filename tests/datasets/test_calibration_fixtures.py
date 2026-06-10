import json
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.judge import build_judge_prompt, prompt_hash
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tasks.schema import AllOf, LlmJudgeSpec
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

FIXTURES = Path("examples/calibration/fixtures.jsonl")
LABELS = Path("examples/calibration/intended_labels.jsonl")


def _load_fixtures():
    return [json.loads(line) for line in FIXTURES.read_text().splitlines() if line.strip()]


def test_fixture_count_in_range() -> None:
    rows = _load_fixtures()
    assert 12 <= len(rows) <= 20


def test_every_fixture_parses_trajectory_and_judge_spec() -> None:
    for row in _load_fixtures():
        traj = trajectory_from_dict(row["trajectory"])
        spec = verification_from_dict(row["verification"])
        # judge spec sits inside an AllOf (coexistence) or stands alone
        if isinstance(spec, AllOf):
            assert any(isinstance(s, LlmJudgeSpec) for s in spec.specs)
        else:
            assert isinstance(spec, LlmJudgeSpec)
        assert traj.turns  # non-empty


def test_intended_labels_cover_at_least_three_anchors_and_match_ids() -> None:
    rows = _load_fixtures()
    labels = {
        json.loads(line)["fixture_id"]: json.loads(line)
        for line in LABELS.read_text().splitlines()
        if line.strip()
    }
    fixture_ids = {row["id"] for row in rows}
    assert set(labels) == fixture_ids  # every fixture has an intended label, no orphans
    anchors = {labels[i]["intended_anchor"] for i in labels}
    assert len(anchors) >= 3


def test_intended_labels_are_not_in_the_fixtures_file() -> None:
    text = FIXTURES.read_text()
    assert "intended_anchor" not in text
    assert "planted_failure" not in text


def test_a_judge_leg_can_be_graded_with_a_supplied_verdict() -> None:
    from agent_eval_lab.graders.judge import JudgeVerdict

    row = _load_fixtures()[0]
    traj = trajectory_from_dict(row["trajectory"])
    spec = verification_from_dict(row["verification"])
    judge = next(
        s for s in (spec.specs if isinstance(spec, AllOf) else (spec,))
        if isinstance(s, LlmJudgeSpec)
    )
    h = prompt_hash(build_judge_prompt(spec=judge, trajectory=traj))
    v = JudgeVerdict(
        score=5, rationale="r", raw="SCORE: 5", judge_model="m", prompt_hash=h
    )
    result = grade_trajectory(
        verification=spec, trajectory=traj, registry=WORKSPACE_TOOLS, verdicts={h: v}
    )
    assert result.grader_id in ("llm_judge", "all_of")
