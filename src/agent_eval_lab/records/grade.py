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


def is_env_invalid_run(run: "RunResult") -> bool:
    """True iff the run is a PROVIDER-side failure (the provider rejected the
    request or returned no completion) — an env-invalidity, never a model failure.

    These are the §18.5/D34 'env-invalid' analogue for any domain that has no live
    health probe: a `chat_completion` HTTP rejection (PROVIDER_ERROR — e.g. a 403
    insufficient-balance or 429 rate-limit) or an empty `choices` (NO_CHOICES_ERROR)
    means the model never got a fair trial, so the run must be masked out of pass^k
    rather than scored as a failure. A genuine model parse failure (unusable
    content/tool_calls) is NOT env-invalid — that is a real model miss.
    """
    pf = run.trajectory.parse_failure
    return pf is not None and pf.error in (PROVIDER_ERROR, NO_CHOICES_ERROR)
