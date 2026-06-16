"""Grading records and the structured failure taxonomy (spec §4.5)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.trajectory import (
    NO_CHOICES_ERROR,
    PROVIDER_ERROR,
    Trajectory,
)

FailureCategory = Literal[
    "malformed_call",
    "schema_violation",
    "wrong_tool",
    "wrong_args",
    "missing_call",
    "extra_call",
    "order_mismatch",
    # The two categories below are forward-declarations: emitted from Weeks 3-4
    # onward by TrajectorySpec/policy grading; the Weeks 1-2 pipeline never
    # produces them.
    "forbidden_action",
    "step_limit_exceeded",
]


@dataclass(frozen=True, kw_only=True)
class GradeResult:
    grader_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any]
    failure_reason: FailureCategory | None = None


@dataclass(frozen=True, kw_only=True)
class RunResult:
    task_id: str
    condition_id: str
    run_index: int
    trajectory: Trajectory
    grade: GradeResult


def _grade_marks_env_invalid(evidence: Mapping[str, Any]) -> bool:
    """True iff this grade evidence — or any nested AllOf sub-result — carries the
    grader-set ``env_invalid`` marker.

    A grader sets ``env_invalid=True`` when the GRADING harness itself could not
    run (e.g. the F3 node oracle hit an incapable node / an oracle exec error), so
    the verdict is not a model judgement at all. ``AllOf`` nests its sub-grades
    under ``evidence['sub_results'][*]['evidence']`` (composite.py), and real F
    verifications always wrap NodeExecutionSpec(s) in an AllOf, so the marker can
    sit one or more levels deep — scan the whole evidence tree. Pure.
    """
    if evidence.get("env_invalid") is True:
        return True
    return any(
        _grade_marks_env_invalid(sub.get("evidence", {}))
        for sub in evidence.get("sub_results", ())
    )


def is_env_invalid_run(run: "RunResult") -> bool:
    """True iff the run never got a fair trial — an env-invalidity, never a model
    failure — and so must be masked out of pass^k (the §18.5/D34 'env-invalid'
    analogue for any domain with no live health probe).

    Two independent sources:

    1. PROVIDER-side (trajectory): a ``chat_completion`` HTTP rejection
       (PROVIDER_ERROR — e.g. a 403 insufficient-balance or 429 rate-limit) or an
       empty ``choices`` (NO_CHOICES_ERROR) means the model never acted.
    2. ORACLE-side (grade): a grader marked its own verdict ``env_invalid`` because
       the grading harness could not run — e.g. the F3 node oracle hit an incapable
       node (``--test-reporter`` unsupported on node < 20) or an oracle exec error.
       Defense-in-depth: even if a fail-fast guard is bypassed, such a run is loudly
       excluded from pass^k rather than silently counted as a model FAIL.

    A genuine model parse failure (unusable content/tool_calls) and a genuine model
    code failure (tests run and fail, or break the code) are NOT env-invalid — those
    are real model misses.
    """
    pf = run.trajectory.parse_failure
    if pf is not None and pf.error in (PROVIDER_ERROR, NO_CHOICES_ERROR):
        return True
    return _grade_marks_env_invalid(run.grade.evidence)
