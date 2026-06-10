"""Pure AllOf interpreter: conjunction over sub-specs (ADR-0003, spec §6).

Evaluates every sub-spec (no short-circuit) so the audit trail sees every
co-occurring breach; passed is the AND; failure_reason is the first failing
sub-spec's; evidence lists all sub-results. The grader function is injected to
keep this module free of a circular import with dispatch.
"""

from collections.abc import Callable, Mapping
from typing import Any

from agent_eval_lab.records.grade import GradeResult
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import AllOf
from agent_eval_lab.tools.workspace import ToolDef

GRADER_ID = "all_of"

GradeFn = Callable[..., GradeResult]


def grade_all_of(
    *,
    spec: AllOf,
    initial_state: Mapping[str, Any] | None,
    trajectory: Trajectory,
    registry: Mapping[str, ToolDef],
    grade: GradeFn,
    verdicts: Mapping[str, Any],
) -> GradeResult:
    """Grade AllOf by recursing `grade` over every sub-spec in declared order."""
    sub_results = tuple(
        grade(
            verification=sub,
            trajectory=trajectory,
            registry=registry,
            initial_state=initial_state,
            verdicts=verdicts,
        )
        for sub in spec.specs
    )
    passed = all(r.passed for r in sub_results)
    first_failure = next((r.failure_reason for r in sub_results if not r.passed), None)
    return GradeResult(
        grader_id=GRADER_ID,
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={
            "sub_results": [
                {
                    "grader_id": r.grader_id,
                    "passed": r.passed,
                    "failure_reason": r.failure_reason,
                    "evidence": dict(r.evidence),
                }
                for r in sub_results
            ]
        },
        failure_reason=first_failure,
    )
