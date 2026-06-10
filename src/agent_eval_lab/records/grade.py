"""Grading records and the structured failure taxonomy (spec §4.5)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.trajectory import Trajectory

FailureCategory = Literal[
    "malformed_call",
    "schema_violation",
    "wrong_tool",
    "wrong_args",
    "missing_call",
    "extra_call",
    "order_mismatch",
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
