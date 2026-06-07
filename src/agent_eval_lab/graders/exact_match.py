"""Deterministic exact-match grading."""

from dataclasses import dataclass


@dataclass(frozen=True)
class GradeResult:
    """Immutable result produced by a grader."""

    passed: bool
    score: float
    feedback: str


def grade_exact_match(*, expected: str, actual: str) -> GradeResult:
    """Grade values that match exactly."""
    if expected == actual:
        return GradeResult(passed=True, score=1.0, feedback="Values match exactly.")

    feedback = f"Expected {expected!r}, received {actual!r}."
    return GradeResult(passed=False, score=0.0, feedback=feedback)
