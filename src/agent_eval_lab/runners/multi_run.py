"""EDGE: run a task k times (multi-run from day 1) and grade every run."""

from collections.abc import Mapping

import httpx

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef


def run_task_k(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    k: int,
    max_steps: int,
    temperature: float,
) -> tuple[RunResult, ...]:
    condition = condition_id(config)
    results = []
    for run_index in range(k):
        trajectory = run_single(
            task=task,
            registry=registry,
            config=config,
            http_client=http_client,
            run_index=run_index,
            max_steps=max_steps,
            temperature=temperature,
        )
        grade = grade_trajectory(
            verification=task.verification,
            trajectory=trajectory,
            registry=registry,
            initial_state=task.initial_state,
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
