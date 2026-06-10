"""OutputMatchSpec scorer (formerly the standalone exact-match grader)."""

from agent_eval_lab.tasks.grading import GradeResult

_GRADER_ID = "output_match"


def grade_exact_match(*, expected: str, actual: str) -> GradeResult:
    """Grade values that match exactly. Survives as the OutputMatchSpec scorer."""
    if expected == actual:
        return GradeResult(
            grader_id=_GRADER_ID,
            passed=True,
            score=1.0,
            evidence={"message": "Values match exactly."},
        )
    return GradeResult(
        grader_id=_GRADER_ID,
        passed=False,
        score=0.0,
        evidence={"message": f"Expected {expected!r}, received {actual!r}."},
        failure_reason="wrong_tool",
    )
