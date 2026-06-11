"""Golden conformance suite: hand-verified trajectories with known grades.

Each JSON case carries a verification spec, a trajectory, and the
hand-verified expected grade. The harness must reproduce the oracle.
Execution cases (item 002) carry `"registry": "code_world"` and grade
through the PRODUCTION oracle edge — real sandboxed pytest per case,
deterministic by ADR-0009.
"""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.graders.execution import collect_execution_specs
from agent_eval_lab.records.serialize import trajectory_from_dict
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.tasks.parse import verification_from_dict
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.workspace import WORKSPACE_TOOLS

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_CASES = sorted(GOLDEN_DIR.glob("*.json"))

REGISTRIES = {"workspace": WORKSPACE_TOOLS, "code_world": CODE_WORLD_TOOLS}


def test_golden_suite_is_present() -> None:
    assert len(GOLDEN_CASES) == 32


@pytest.mark.parametrize("path", GOLDEN_CASES, ids=lambda p: p.stem)
def test_golden_conformance(path: Path) -> None:
    case = json.loads(path.read_text())
    verification = verification_from_dict(case["verification"])
    trajectory = trajectory_from_dict(case["trajectory"])

    grade = grade_trajectory(
        verification=verification,
        trajectory=trajectory,
        registry=REGISTRIES[case.get("registry", "workspace")],
        initial_state=case.get("initial_state"),
        verdicts=precompute_execution_verdicts(
            verification=verification, trajectory=trajectory
        ),
    )

    assert grade.passed == case["expected"]["passed"], (
        f"{case['name']}: passed={grade.passed!r}, "
        f"expected={case['expected']['passed']!r}"
    )
    assert grade.failure_reason == case["expected"]["failure_reason"], (
        f"{case['name']}: failure_reason={grade.failure_reason!r}, "
        f"expected={case['expected']['failure_reason']!r}"
    )


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def test_oracle_contents_never_appear_in_any_trajectory_turn() -> None:
    """Security constraint: held-out oracle tests are never agent-visible."""
    oracle_files_checked = 0
    for path in GOLDEN_CASES:
        case = json.loads(path.read_text())
        specs = collect_execution_specs(verification_from_dict(case["verification"]))
        turn_texts = _strings(case["trajectory"]["turns"])
        for spec in specs:
            for content in spec.held_out_tests.values():
                assert all(content not in text for text in turn_texts), path.stem
                oracle_files_checked += 1
    assert oracle_files_checked >= 9  # every execution golden was exercised
