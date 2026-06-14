"""EDGE: M1 run orchestration — conditions × domains over the runners.

For each ProviderConfig and each domain with task definitions, run the domain's
tasks and collect ReplacementOutcomes. D uses runners/dset_run.run_dset (the
template domain path). F and B are WIRED WHEN ITEMS 004/006 LAND: a domain with
no task definitions is simply skipped (absent, not a crash) so the D-only first
run works today. The actual provider/network calls happen here; this module is
unit-tested with run_dset STUBBED (the real multi-model run is downstream, out
of scope for this item).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

import httpx

from agent_eval_lab.runners.b_run import run_b
from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.dset_run import run_dset
from agent_eval_lab.runners.f_run import prefix_candidate_tree, run_f
from agent_eval_lab.runners.mstr_client import MstrReadbackClient
from agent_eval_lab.runners.multi_run import ReplacementOutcome
from agent_eval_lab.tasks.schema import Task


def run_m1(
    *,
    configs: Sequence[ProviderConfig],
    domain_tasks: Mapping[str, Sequence[Task]],
    http_client: httpx.Client,
    k_valid: int,
    max_invalid_rate: float,
    temperature: float,
    max_tokens: int,
    health_probe_fn: Callable | None,
    reference_sha256: str | None,
    evaluator_store: Path | None,
    f_repo: Path | None = None,
    b_client: MstrReadbackClient | None = None,
    b_project_id: str | None = None,
    b_folder: str | None = None,
) -> dict[str, dict[str, tuple[ReplacementOutcome, ...]]]:
    out: dict[str, dict[str, tuple[ReplacementOutcome, ...]]] = {}
    for config in configs:
        cond = condition_id(config)
        out[cond] = {}
        d_tasks = domain_tasks.get("D")
        if d_tasks:
            # run_dset yields per task (incremental-write contract); collect into a
            # tuple here to keep run_m1's by-condition/by-domain mapping return shape.
            out[cond]["D"] = tuple(
                run_dset(
                    evaluator_store=evaluator_store,
                    tasks=tuple(d_tasks),
                    config=config,
                    http_client=http_client,
                    k_valid=k_valid,
                    max_invalid_rate=max_invalid_rate,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    health_probe_fn=health_probe_fn,
                    reference_sha256=reference_sha256,
                )
            )
        f_tasks = domain_tasks.get("F")
        if f_tasks and f_repo is not None:

            def _build_tree(task):
                # POST-MERGE execute phase produces the model's edited tree here;
                # absent a candidate edit, grade the pinned base tree (deterministic).
                return prefix_candidate_tree(task, repo=f_repo)

            out[cond]["F"] = tuple(
                run_f(tasks=tuple(f_tasks), build_tree_fn=_build_tree, k=k_valid)
            )
        b_tasks = domain_tasks.get("B")
        if b_tasks and b_client is not None and b_project_id is not None:
            out[cond]["B"] = tuple(
                run_b(
                    tasks=tuple(b_tasks),
                    client=b_client,
                    project_id=b_project_id,
                    folder=b_folder or "/runs",
                    condition_id=cond,
                    k=k_valid,
                )
            )
        # Absent B tasks/client -> skipped, never a crash (mirrors the F branch).
    return out
