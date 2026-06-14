"""EDGE: run the F-domain repo-fix tasks and grade them via the node oracle.

Per F task: a candidate file tree is produced (build_tree_fn — the model's edit at
execute time; injectable so tests stub it), graded by the held-out NodeExecutionSpec
via precompute_node_verdicts + grade_trajectory, and wrapped one ReplacementOutcome
per task (k valid runs of the SAME deterministic tree — the node oracle is env-free
so every trial is valid and identical; pass^k is well-defined). The candidate base is
pinned to 5b0c13a6 (D32) via prefix_candidate_tree; m2021 HEAD is never read.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path

from agent_eval_lab.graders.dispatch import grade_trajectory
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.runners.node_oracle_edge import precompute_node_verdicts
from agent_eval_lab.tasks.schema import Task

CANDIDATE_BASE_SHA = "5b0c13a6bc9e7b9a3c60083da511f3efd0d39505"


def prefix_candidate_tree(task: Task, *, repo: Path) -> dict[str, str]:
    """Reconstruct the candidate workspace at the pinned base SHA (D32).

    Reads ONLY the task's target_paths from `git show 5b0c13a6:<path>` plus the
    minimal tests/wdio/package.json. Never checks out; never reads m2021 HEAD.
    """
    assert task.initial_state is not None
    assert task.initial_state["candidate_base_sha"] == CANDIDATE_BASE_SHA
    tree: dict[str, str] = {"tests/wdio/package.json": '{"type":"module"}\n'}
    for rel in task.initial_state["target_paths"]:
        tree[rel] = subprocess.run(
            ["git", "-C", str(repo), "show", f"{CANDIDATE_BASE_SHA}:{rel}"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    return tree


def _grade_tree(task: Task, files: Mapping[str, str]) -> RunResult:
    traj = Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
        final_state={"files": dict(files)},
    )
    verdicts = precompute_node_verdicts(verification=task.verification, trajectory=traj)
    grade = grade_trajectory(
        verification=task.verification, trajectory=traj, registry={}, verdicts=verdicts
    )
    return RunResult(
        task_id=task.id,
        condition_id="(f-local)",
        run_index=0,
        trajectory=traj,
        grade=grade,
    )


def run_f(
    *,
    tasks: Sequence[Task],
    build_tree_fn: Callable[[Task], Mapping[str, str]],
    k: int,
) -> Iterator[ReplacementOutcome]:
    """Yield one ReplacementOutcome per F task (env-free → k identical valid runs)."""
    for task in tasks:
        files = build_tree_fn(task)
        run = _grade_tree(task, files)
        runs = tuple(
            RunResult(
                task_id=run.task_id,
                condition_id=run.condition_id,
                run_index=i,
                trajectory=run.trajectory,
                grade=run.grade,
            )
            for i in range(k)
        )
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
        )
        yield ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)
