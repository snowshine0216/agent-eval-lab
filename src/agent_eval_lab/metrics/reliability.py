"""pass@1 (trial accuracy) and pass^k (task-level reliability), spec §4.6.

A task passes pass^k iff ALL of its runs pass; the estimand is the
proportion of tasks that pass every run — not trial-level accuracy.
"""

import random
from collections.abc import Mapping, Sequence

# Reuse BootstrapCI shape + _percentile from agreement.py (internal helper,
# no behavior change — spec permits import rather than extraction).
from agent_eval_lab.metrics.agreement import BootstrapCI, _percentile
from agent_eval_lab.records.grade import RunResult


def _require_results(results: Sequence[RunResult]) -> None:
    if not results:
        raise ValueError("no results to aggregate")


def _run_passes(run: RunResult) -> bool:
    """A run counts as a pass iff it graded-passed AND was not budget-capped.

    Enforces the pass_pow_k MetricDef's declared censoring_policy="failure"
    (§D.1). safety_cap_bound already exists on the trajectory; max_rounds_bound
    arrives in item 002, so it is read DEFENSIVELY (default False) — every
    existing record (which lacks the field) is unaffected. The censor is GLOBAL
    by design (§10.6): D/B inherit it through this shared module and the Fisher-F
    path in comparisons.py, which both route through task_reliability.
    """
    traj = run.trajectory
    capped = traj.safety_cap_bound or getattr(traj, "max_rounds_bound", False)
    return run.grade.passed and not capped


def pass_at_1(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(1 for run in results if run.grade.passed) / len(results)


def pass_pow_k(results: Sequence[RunResult]) -> float:
    _require_results(results)
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(_run_passes(run))
    reliable = sum(1 for passes in by_task.values() if all(passes))
    return reliable / len(by_task)


def failure_counts(results: Sequence[RunResult]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for run in results:
        if run.grade.passed:
            continue
        key = run.grade.failure_reason or "unclassified"
        counts[key] = counts.get(key, 0) + 1
    return counts


def token_totals(results: Sequence[RunResult]) -> tuple[int, int]:
    prompt = sum(run.trajectory.usage.prompt_tokens for run in results)
    completion = sum(run.trajectory.usage.completion_tokens for run in results)
    return prompt, completion


def mean_latency_s(results: Sequence[RunResult]) -> float:
    _require_results(results)
    return sum(run.trajectory.usage.latency_s for run in results) / len(results)


def task_reliability(results: Sequence[RunResult]) -> dict[str, bool]:
    """Map each task id to whether ALL its runs passed-uncensored (its pass^k
    indicator). A run passes iff grade.passed AND not budget-capped (§D.1)."""
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(_run_passes(run))
    return {tid: all(passes) for tid, passes in by_task.items()}


# Back-compat alias — call sites that used the private name continue to work.
_task_reliability = task_reliability


def pass_pow_k_bootstrap_ci(
    results: Sequence[RunResult],
    *,
    n_resamples: int,
    seed: int,
    alpha: float,
) -> BootstrapCI:
    """Cluster-bootstrap-by-task percentile CI for pass^k (spec §4.6). Resample
    the SET of task ids with replacement; recompute pass^k over the resampled
    multiset. The task is the unit because the k runs of one task move together.
    Seeded RNG => deterministic. No 1-p_e degeneracy class (Resolved Q2):
    n_degenerate is always 0; an all-pass/all-fail resample is a legitimate
    pass^k of 1.0/0.0."""
    _require_results(results)
    reliable = _task_reliability(results)
    ids = list(reliable)
    n = len(ids)
    rng = random.Random(seed)
    point = sum(reliable.values()) / n
    samples: list[float] = []
    for _ in range(n_resamples):
        drawn = [ids[rng.randrange(n)] for _ in range(n)]
        samples.append(sum(reliable[tid] for tid in drawn) / n)
    samples.sort()
    return BootstrapCI(
        point=point,
        lo=_percentile(samples, alpha / 2),
        hi=_percentile(samples, 1 - alpha / 2),
        alpha=alpha,
        n_resamples=n_resamples,
        n_degenerate=0,
        seed=seed,
    )


def paired_pass_pow_k_diff_ci(
    results_a: Sequence[RunResult],
    results_b: Sequence[RunResult],
    *,
    n_resamples: int,
    seed: int,
    alpha: float,
) -> BootstrapCI:
    """Cluster-bootstrap-by-task percentile CI for Δ = pass^k(B) − pass^k(A) on
    PAIRED tasks (spec §4.6, Resolved Q1). Requires both inputs to cover the
    identical task-id universe and raises on mismatch (no silent half-pairing).
    Each iteration draws ONE task-id multiset and applies it to both configs, so
    within-task pairing is structural. n_degenerate is always 0 (Resolved Q2)."""
    _require_results(results_a)
    _require_results(results_b)
    rel_a = _task_reliability(results_a)
    rel_b = _task_reliability(results_b)
    if set(rel_a) != set(rel_b):
        raise ValueError(
            "paired diff requires an identical task-id universe across "
            f"results_a and results_b; got {sorted(rel_a)} vs {sorted(rel_b)}"
        )
    ids = list(rel_a)
    n = len(ids)
    rng = random.Random(seed)
    point = (sum(rel_b.values()) - sum(rel_a.values())) / n
    samples: list[float] = []
    for _ in range(n_resamples):
        drawn = [ids[rng.randrange(n)] for _ in range(n)]
        pa = sum(rel_a[tid] for tid in drawn) / n
        pb = sum(rel_b[tid] for tid in drawn) / n
        samples.append(pb - pa)
    samples.sort()
    return BootstrapCI(
        point=point,
        lo=_percentile(samples, alpha / 2),
        hi=_percentile(samples, 1 - alpha / 2),
        alpha=alpha,
        n_resamples=n_resamples,
        n_degenerate=0,
        seed=seed,
    )


def tier_of(task_id: str, tiers: Mapping[str, str]) -> str:
    """Look up a task's tier from the committed sidecar map; raises if unmapped
    (the report must never silently drop a task from its tier axis)."""
    try:
        return tiers[task_id]
    except KeyError as exc:
        raise ValueError(f"task {task_id!r} has no tier in the sidecar") from exc


def pass_pow_k_by_tier(
    results: Sequence[RunResult], tiers: Mapping[str, str]
) -> dict[str, float]:
    """pass^k computed per tier. Tiers with no results are omitted."""
    by_tier: dict[str, list[RunResult]] = {}
    for run in results:
        by_tier.setdefault(tier_of(run.task_id, tiers), []).append(run)
    return {tier: pass_pow_k(runs) for tier, runs in sorted(by_tier.items())}
