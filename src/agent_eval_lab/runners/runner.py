"""Multi-run model<->tool loop (imperative shell).

Threads world state explicitly via tools.apply, enforces limits, runs k runs per
task, grades each, and emits RunResult records. Deterministic given a FakeModel.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent_eval_lab.graders.grade import grade_trajectory
from agent_eval_lab.runners.fake_model import FakeModel
from agent_eval_lab.tasks.grading import GradeResult, RunResult, Trajectory
from agent_eval_lab.tasks.task import Task
from agent_eval_lab.tasks.turns import (
    MessageTurn,
    ToolCallTurn,
    ToolResultTurn,
)
from agent_eval_lab.tools.workspace_world import apply

_COST_PER_1K_TOKENS = 0.0005  # fixed synthetic price for the fake model


@dataclass(frozen=True, kw_only=True)
class RunLimits:
    max_turns: int = 8
    max_tool_calls: int = 8


def _cost(total_tokens: int) -> float:
    return round((total_tokens / 1000) * _COST_PER_1K_TOKENS, 8)


def _execute(
    task: Task,
    model: FakeModel,
    schemas: Mapping[str, Any],
    run_index: int,
    limits: RunLimits,
) -> RunResult:
    state = dict(task.initial_state or {})
    turns: list[Any] = []
    total_tokens = 0
    tool_calls_made = 0
    termination = "stop"
    for step in range(model.num_steps(task.id)):
        if len(turns) >= limits.max_turns:
            termination = "max_turns"
            break
        turn, usage = model.respond_with_usage(task_id=task.id, step=step)
        total_tokens += usage.get("total_tokens", 0)
        turns.append(turn)
        if isinstance(turn, ToolCallTurn):
            if tool_calls_made + len(turn.tool_calls) > limits.max_tool_calls:
                termination = "max_tool_calls"
                break
            for call in turn.tool_calls:
                state, outcome = apply(call.name, call.arguments, state)
                turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))
                tool_calls_made += 1
        elif isinstance(turn, MessageTurn):
            termination = "stop"
            break
    trajectory = Trajectory(
        turns=tuple(turns),
        usage={"total_tokens": total_tokens},
        cost_usd=_cost(total_tokens),
        latency_ms=total_tokens,  # deterministic synthetic latency proxy
        run_index=run_index,
        termination_reason=termination,
    )
    grade = _grade(task, trajectory, schemas, termination)
    return RunResult(
        task_id=task.id,
        condition_id=task.metadata.split,
        run_index=run_index,
        trajectory=trajectory,
        grade=grade,
    )


def _grade(
    task: Task, trajectory: Trajectory, schemas: Mapping[str, Any], termination: str
) -> GradeResult:
    if termination in ("max_turns", "max_tool_calls"):
        return GradeResult(
            grader_id="runner",
            passed=False,
            score=0.0,
            evidence={"termination_reason": termination},
            failure_reason="step_limit_exceeded",
        )
    return grade_trajectory(task.verification, trajectory.turns, schemas)


def run_task(
    task: Task,
    model: FakeModel,
    schemas: Mapping[str, Any],
    *,
    k: int,
    limits: RunLimits,
) -> list[RunResult]:
    """Run the task k times under the given limits; emit one RunResult per run."""
    return [_execute(task, model, schemas, i, limits) for i in range(k)]
