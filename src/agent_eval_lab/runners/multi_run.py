"""EDGE: run a task k times (multi-run from day 1) and grade every run."""

from collections.abc import Mapping

import httpx

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import ApplyFn, Executor, run_single
from agent_eval_lab.runners.oracle_edge import precompute_execution_verdicts
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef
from agent_eval_lab.tools.workspace import apply as workspace_apply


def effective_max_steps(task: Task, *, default: int) -> int:
    """ADR-0004: the per-task metadata.max_steps WINS when present; the CLI
    default is the fallback for tasks without one (a floor, never a cap)."""
    declared = task.metadata.max_steps
    return declared if declared is not None else default


def run_task_k(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k: int,
    max_steps: int,
    temperature: float,
    max_tokens: int,
    apply_fn: ApplyFn = workspace_apply,
    executor: Executor | None = None,
) -> tuple[RunResult, ...]:
    # The world-binding fields (item 004 criterion 3) default to today's
    # workspace behavior exactly; cli.run_baseline threads the resolved
    # binding's fields per task (runners/worlds.resolve_world).
    condition = condition_id(config)
    budget = effective_max_steps(task, default=max_steps)
    results = []
    for run_index in range(k):
        trajectory = run_single(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            max_steps=budget,
            temperature=temperature,
            max_tokens=max_tokens,
            apply_fn=apply_fn,
            executor=executor,
        )
        # ADR-0011: the oracle edge precomputes execution verdicts
        # post-trajectory; {} for tasks with no ExecutionSpec, so
        # non-execution tasks grade byte-identically to before.
        verdicts = precompute_execution_verdicts(
            verification=task.verification, trajectory=trajectory
        )
        grade = grade_trajectory(
            verification=task.verification,
            trajectory=trajectory,
            registry=registry,
            initial_state=task.initial_state,
            verdicts=verdicts,
        )
        results.append(
            RunResult(
                task_id=task.id,
                condition_id=condition,
                run_index=run_index,
                trajectory=trajectory,
                grade=grade,
            )
        )
    return tuple(results)
