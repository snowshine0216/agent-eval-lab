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

from agent_eval_lab.runners.config import ProviderConfig, condition_id
from agent_eval_lab.runners.dset_run import run_dset
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
) -> dict[str, dict[str, tuple[ReplacementOutcome, ...]]]:
    out: dict[str, dict[str, tuple[ReplacementOutcome, ...]]] = {}
    for config in configs:
        cond = condition_id(config)
        out[cond] = {}
        d_tasks = domain_tasks.get("D")
        if d_tasks:
            out[cond]["D"] = run_dset(
                evaluator_store=evaluator_store, tasks=tuple(d_tasks), config=config,
                http_client=http_client, k_valid=k_valid,
                max_invalid_rate=max_invalid_rate, temperature=temperature,
                max_tokens=max_tokens, health_probe_fn=health_probe_fn,
                reference_sha256=reference_sha256,
            )
        # F / B: no domain runner yet (items 004/006). Absent -> skipped, never a crash.
    return out
