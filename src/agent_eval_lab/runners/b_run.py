"""EDGE: run the B-domain MSTR readback tasks and grade them via the readback
oracle. Mirrors runners/f_run.run_f.

Per B task, the per-run isolation lifecycle (D20) runs over the injectable
MstrReadbackClient: derive the save-name from run_uid, preflight-assert the name
is absent (occupied => VOID, never scored), capture the created object id on save,
read it back under the expected prompt, grade with grade_b1_readback, then reset.
The live readback is the injected client; tests pass a deterministic fake (no live
MSTR I/O). The grader keys on the CAPTURED object id, never a name search.

This is the WIRING + deterministic grade path. The LIVE model-driven build (the
candidate actually clicking through the Library UI) is the DEFERRED execute phase
(EXECUTE-DEFERRED); there, the client is the evaluator-credentialed playwright-cli
readback and the run_uid comes from the live Trajectory."""

from __future__ import annotations

from collections.abc import Iterator, Sequence

from agent_eval_lab.datasets.b1_oracle import grade_b1_readback
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.runners.b_isolation import (
    capture_created_id,
    preflight_absent,
    reset_after_grading,
    save_name_from_run_uid,
)
from agent_eval_lab.runners.mstr_client import MstrReadbackClient, SaveTarget
from agent_eval_lab.runners.multi_run import ReplacementOutcome, TrialAttempt
from agent_eval_lab.tasks.schema import ReadbackSpec, Task


def _empty_trajectory(run_index: int, run_uid: str) -> Trajectory:
    return Trajectory(
        turns=(),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=run_index,
        stop_reason="completed",
        run_uid=run_uid,
    )


def run_b(
    *,
    tasks: Sequence[Task],
    client: MstrReadbackClient,
    project_id: str,
    folder: str,
    condition_id: str,
    k: int,
) -> Iterator[ReplacementOutcome]:
    """Yield one ReplacementOutcome per B task (D20 isolation + readback grade).

    A preflight-occupied save target is an isolation invalidity -> VOID outcome
    (never scored over a contaminated run). Otherwise: capture the created object
    id, read it back, grade, reset, and wrap k identical valid runs (the readback
    of a fixed object is deterministic, so pass^k is well-defined here)."""
    for task_index, task in enumerate(tasks):
        assert isinstance(task.verification, ReadbackSpec)
        # Each task gets a DISTINCT per-task save-name (D20: unique per-arm,
        # not reliant on reset timing). task_index drives uniqueness here;
        # __0000 → noskill arm, __0001 → skill arm for B-1 (two-task set).
        # NOTE: the live per-trial run_uid (k replacement trials of one saved
        # object) is a separate axis and remains deferred (EXECUTE-DEFERRED).
        run_uid = f"{condition_id}__{task_index:04d}"
        name = save_name_from_run_uid(run_uid)
        target = SaveTarget(project_id=project_id, folder=folder, name=name)
        try:
            preflight_absent(client, target)
        except ValueError:
            yield ReplacementOutcome(valid_runs=(), attempts=(), void=True)
            continue
        object_id = capture_created_id(client, target)
        result = client.readback(
            project_id=project_id,
            object_id=object_id,
            prompt=task.verification.expected_prompt,
        )
        grade = grade_b1_readback(task.verification, result)
        reset_after_grading(client, project_id=project_id, object_id=object_id)

        runs = tuple(
            RunResult(
                task_id=task.id,
                condition_id=condition_id,
                run_index=i,
                trajectory=_empty_trajectory(i, f"{condition_id}__{i:04d}"),
                grade=grade,
            )
            for i in range(k)
        )
        attempts = tuple(
            TrialAttempt(attempt_index=i, valid=True, run=r) for i, r in enumerate(runs)
        )
        yield ReplacementOutcome(valid_runs=runs, attempts=attempts, void=False)
