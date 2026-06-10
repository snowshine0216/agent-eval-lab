"""Grading + run records (design §4.5). Tool-use subset of FailureCategory."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_eval_lab.tasks.turns import Turn

FailureCategory = Literal[
    "malformed_call",
    "schema_violation",
    "wrong_tool",
    "wrong_args",
    "missing_call",
    "extra_call",
    "order_mismatch",
    "step_limit_exceeded",
]


@dataclass(frozen=True, kw_only=True)
class GradeResult:
    grader_id: str
    passed: bool
    score: float
    evidence: Mapping[str, Any] = field(default_factory=dict)
    failure_reason: FailureCategory | None = None


@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Mapping[str, int]  # {prompt_tokens, completion_tokens, total_tokens}
    cost_usd: float
    latency_ms: int
    run_index: int
    termination_reason: Literal["stop", "max_turns", "max_tool_calls"]


@dataclass(frozen=True, kw_only=True)
class RunResult:
    task_id: str
    condition_id: str
    run_index: int
    trajectory: Trajectory
    grade: GradeResult
