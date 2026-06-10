"""Golden conformance suite: hand-verified trajectories with known grades.

Each JSON case carries a verification spec, a trajectory, and the
hand-verified expected grade. The harness must reproduce the oracle.
"""

import json
from pathlib import Path

import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_CASES = sorted(GOLDEN_DIR.glob("*.json"))


def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 23


@pytest.mark.parametrize("path", GOLDEN_CASES, ids=lambda p: p.stem)
def test_golden_conformance(path: Path) -> None:
    case = json.loads(path.read_text())

    grade = grade_trajectory(
        verification=verification_from_dict(case["verification"]),
        trajectory=trajectory_from_dict(case["trajectory"]),
        registry=WORKSPACE_TOOLS,
        initial_state=case.get("initial_state"),
    )

    assert grade.passed == case["expected"]["passed"], (
        f"{case['name']}: passed={grade.passed!r}, "
        f"expected={case['expected']['passed']!r}"
    )
    assert grade.failure_reason == case["expected"]["failure_reason"], (
        f"{case['name']}: failure_reason={grade.failure_reason!r}, "
        f"expected={case['expected']['failure_reason']!r}"
    )
