"""EDGE: run a model over the D-set via the k_valid replacement loop (§4.2 / D34).

Each task runs under run_task_k_valid with: a per-task stateful bash executor
(one playwright-cli session + isolated workdir per task), the §18.5 health-probe
validity mask, and a snapshot-hash validity_fn (D36 — a live-page hash mismatch
at run start marks the run env-invalid, excluded from pass^k). Records carry
rounds/tokens/cost via the unchanged Trajectory fields (item 001).
"""

import re
from collections.abc import Callable, Iterator
from pathlib import Path

import httpx

from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.runners.bash_edge import make_bash_executor
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.multi_run import ReplacementOutcome, run_task_k_valid
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.browse import BROWSE_TOOLS, apply_browse


def make_snapshot_validity_fn(*, reference_sha256: str) -> Callable[[RunResult], bool]:
    """A run is valid iff its recorded page-snapshot hash matches the reference
    (D36). The hash is recorded in the fact-key grade evidence; a mismatch means
    the live docs drifted from the frozen snapshot -> env-invalid, not model."""

    def validity_fn(run: RunResult) -> bool:
        recorded = run.grade.evidence.get("page_snapshot_sha256")
        # Only a CONFIRMED snapshot mismatch is env drift (-> invalid, replace).
        # A run with no recorded snapshot (model produced no answer / failed
        # before grading) is NOT env-invalid — it's a valid trial the model
        # failed; treating it as invalid would mask model failures and could
        # spuriously VOID the task (review L1).
        if recorded is None:
            return True
        return recorded == reference_sha256

    return validity_fn


def _condition_id_slug(condition: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", condition)


def run_dset(
    *,
    evaluator_store: Path,
    tasks: tuple[Task, ...],
    config: ProviderConfig,
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    temperature: float,
    max_tokens: int,
    health_probe_fn: "Callable | None" = None,
    reference_sha256: str | None = None,
    heartbeat_fn: "Callable[[str], None] | None" = None,
) -> Iterator[ReplacementOutcome]:
    """Run every D-set task k_valid times; YIELD one ReplacementOutcome per task as
    it completes, so the caller can persist incrementally — one bad task can no
    longer abort and lose a whole model's run (the GLM-5.1 pilot lost its data
    because runs were written only at the end).

    A fresh bash executor (isolated session + workdir) is built per task and
    closed after; the snapshot-hash validity_fn (when reference_sha256 is given)
    routes live-docs drift to the validity mask. heartbeat_fn is threaded into
    every per-task executor as a sub-task liveness signal (the per-task yield is
    too coarse a progress signal for a stall watchdog — see bash_edge).
    """
    cond = condition_id(config)
    validity_fn = (
        make_snapshot_validity_fn(reference_sha256=reference_sha256)
        if reference_sha256 is not None
        else None
    )
    for task in tasks:
        workdir = (
            evaluator_store / "dset-work" / f"{_condition_id_slug(cond)}__{task.id}"
        )
        executor, close = make_bash_executor(
            session_id=task.id, workdir=workdir, heartbeat_fn=heartbeat_fn
        )
        try:
            outcome = run_task_k_valid(
                task=task,
                registry=BROWSE_TOOLS,
                config=config,
                http_client=http_client,
                k_valid=k_valid,
                max_invalid_rate=max_invalid_rate,
                max_steps=0,  # unused: the censoring safety cap governs
                temperature=temperature,
                max_tokens=max_tokens,
                validity_fn=validity_fn,
                health_probe_fn=health_probe_fn,
                apply_fn=apply_browse,
                executor=executor,
            )
        finally:
            close()
        yield outcome
