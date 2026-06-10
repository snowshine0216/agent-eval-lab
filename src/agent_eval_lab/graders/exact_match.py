"""Deterministic exact-match grading (the OutputMatchSpec scorer)."""

from agent_eval_lab.records.grade import GradeResult


def grade_exact_match(*, expected: str, actual: str) -> GradeResult:
    """Grade values that match exactly."""
    passed = expected == actual
    return GradeResult(
        grader_id="output_match",
        passed=passed,
        score=1.0 if passed else 0.0,
        evidence={"expected": expected, "actual": actual},
        failure_reason=None,
    )
