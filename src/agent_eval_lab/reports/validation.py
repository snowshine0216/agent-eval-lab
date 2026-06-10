"""Pure failure-mode / validation report (item 004). Build + render, no I/O.

Inputs: per-condition RunResult sequences (read from streamed JSONL at the
edge), the committed tier sidecar, and a capability map. Produces per-condition
pass@1 / pass^k with cluster-bootstrap-by-task CIs, the failure taxonomy crossed
by tier and capability, the per-task pass matrix, the deterministic-vs-flaky
split, per-tier pass^k curves, and the mechanical discriminativeness verdict
(Resolved Q9). A partial condition is `incomplete` (graded over present records,
never blocked); a zero-record condition is `blocked` (no fabricated numbers).
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from agent_eval_lab.metrics.agreement import BootstrapCI
from agent_eval_lab.metrics.reliability import (
    pass_at_1,
    pass_pow_k_bootstrap_ci,
    pass_pow_k_by_tier,
    tier_of,
)
from agent_eval_lab.records.grade import RunResult

TIER_ORDER = ("T1", "T2", "T3", "T4")


@dataclass(frozen=True, kw_only=True)
class ConditionInput:
    label: str
    results: Sequence[RunResult] = field(default_factory=tuple)
    hosted: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ConditionReport:
    label: str
    hosted: bool
    status: str  # "complete" | "incomplete" | "blocked"
    n_tasks: int
    n_runs: int
    blocked_reason: str | None
    pass_at_1: float | None
    pass_pow_k: BootstrapCI | None
    pass_pow_k_by_tier: Mapping[str, float]
    failure_taxonomy: Mapping[tuple, int]  # (category, tier, capability)
    pass_matrix: Mapping[str, bool]  # task_id -> reliable (all-k-pass)
    deterministic_failures: tuple[str, ...]
    flaky_tasks: tuple[str, ...]
    tier_monotone: bool


@dataclass(frozen=True, kw_only=True)
class Discriminativeness:
    rung: str  # "none" | "weak" | "strong"
    weak_met: bool
    strong_met: bool
    strong_pair: tuple[str, str] | None
    strong_pair_ci: BootstrapCI | None
    monotone_conditions: tuple[str, ...]
    detail: str


@dataclass(frozen=True, kw_only=True)
class ValidationReport:
    k: int
    expected_n_tasks: int
    seed: int
    conditions: tuple[ConditionReport, ...]
    discriminativeness: Discriminativeness


def _task_reliability(results: Sequence[RunResult]) -> dict[str, bool]:
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(run.grade.passed)
    return {tid: all(passes) for tid, passes in by_task.items()}


def _task_all_fail(results: Sequence[RunResult]) -> dict[str, bool]:
    by_task: dict[str, list[bool]] = {}
    for run in results:
        by_task.setdefault(run.task_id, []).append(run.grade.passed)
    return {tid: not any(passes) for tid, passes in by_task.items()}


def _build_condition(
    cond: ConditionInput,
    *,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> ConditionReport:
    if cond.blocked_reason is not None or not cond.results:
        return ConditionReport(
            label=cond.label,
            hosted=cond.hosted,
            status="blocked",
            n_tasks=0,
            n_runs=0,
            blocked_reason=cond.blocked_reason or "no reachable records",
            pass_at_1=None,
            pass_pow_k=None,
            pass_pow_k_by_tier={},
            failure_taxonomy={},
            pass_matrix={},
            deterministic_failures=(),
            flaky_tasks=(),
            tier_monotone=False,
        )
    reliable = _task_reliability(cond.results)
    all_fail = _task_all_fail(cond.results)
    n_tasks = len(reliable)
    status = "complete" if n_tasks == expected_n_tasks else "incomplete"
    taxonomy: dict[tuple, int] = {}
    for run in cond.results:
        if run.grade.passed:
            continue
        cat = run.grade.failure_reason or "unclassified"
        key = (cat, tier_of(run.task_id, tiers), capabilities.get(run.task_id, "?"))
        taxonomy[key] = taxonomy.get(key, 0) + 1
    deterministic = tuple(sorted(t for t, af in all_fail.items() if af))
    flaky = tuple(sorted(t for t in reliable if not reliable[t] and not all_fail[t]))
    by_tier = pass_pow_k_by_tier(cond.results, tiers)
    present = [by_tier[t] for t in TIER_ORDER if t in by_tier]
    monotone = all(a >= b for a, b in zip(present, present[1:]))
    return ConditionReport(
        label=cond.label,
        hosted=cond.hosted,
        status=status,
        n_tasks=n_tasks,
        n_runs=len(cond.results),
        blocked_reason=None,
        pass_at_1=pass_at_1(cond.results),
        pass_pow_k=pass_pow_k_bootstrap_ci(
            cond.results, n_resamples=n_resamples, seed=seed, alpha=alpha
        ),
        pass_pow_k_by_tier=by_tier,
        failure_taxonomy=taxonomy,
        pass_matrix=reliable,
        deterministic_failures=deterministic,
        flaky_tasks=flaky,
        tier_monotone=monotone and len(present) >= 2,
    )


def _discriminativeness(
    conditions: Sequence[ConditionReport],
    *,
    raw: Mapping[str, ConditionInput],
    seed: int,
    n_resamples: int,
    alpha: float,
) -> Discriminativeness:
    from agent_eval_lab.metrics.reliability import paired_pass_pow_k_diff_ci

    hosted = [c for c in conditions if c.hosted and c.status != "blocked"]
    # Weak rung: ≥1 task where hosted pass^3 differ AND ≥1 hosted pass^3 < 1.000.
    any_sub_one = any(
        c.pass_pow_k is not None and c.pass_pow_k.point < 1.0 for c in hosted
    )
    differ = False
    for i in range(len(hosted)):
        for j in range(i + 1, len(hosted)):
            mi, mj = hosted[i].pass_matrix, hosted[j].pass_matrix
            shared = set(mi) & set(mj)
            if any(mi[t] != mj[t] for t in shared):
                differ = True
    weak_met = differ and any_sub_one
    # Strong rung A: ≥1 hosted PAIR separated by a paired CI excluding 0.
    strong_pair = None
    strong_pair_ci = None
    for i in range(len(hosted)):
        for j in range(i + 1, len(hosted)):
            ra = raw[hosted[i].label].results
            rb = raw[hosted[j].label].results
            if set(_task_reliability(ra)) != set(_task_reliability(rb)):
                continue  # unequal universe -> not a clean paired comparison
            ci = paired_pass_pow_k_diff_ci(
                ra, rb, n_resamples=n_resamples, seed=seed, alpha=alpha
            )
            if ci.lo > 0 or ci.hi < 0:
                strong_pair = (hosted[i].label, hosted[j].label)
                strong_pair_ci = ci
                break
        if strong_pair is not None:
            break
    # Strong rung B: per-tier monotone non-increasing for ≥1 hosted condition.
    monotone_conditions = tuple(c.label for c in hosted if c.tier_monotone)
    strong_met = strong_pair is not None or len(monotone_conditions) > 0
    rung = "strong" if strong_met else ("weak" if weak_met else "none")
    if rung == "strong":
        detail = (
            "v2 discriminates: a hosted pair is separated by a paired-CI-excluding-0 "
            "gap and/or a hosted condition shows a monotone non-increasing tier "
            "gradient."
        )
    elif rung == "weak":
        hosted_n = max((c.n_tasks for c in hosted), default=0)
        detail = (
            "v2 is no longer saturated (≥1 hosted pass^3 < 1.000 and the hosted "
            "conditions differ on ≥1 task), but the separation is within noise at "
            f"n={hosted_n}."
        )
    else:
        detail = "Hosted conditions remain indistinguishable (no rung met)."
    return Discriminativeness(
        rung=rung,
        weak_met=weak_met,
        strong_met=strong_met,
        strong_pair=strong_pair,
        strong_pair_ci=strong_pair_ci,
        monotone_conditions=monotone_conditions,
        detail=detail,
    )


def build_validation_report(
    *,
    conditions: Sequence[ConditionInput],
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> ValidationReport:
    built = tuple(
        _build_condition(
            c,
            tiers=tiers,
            capabilities=capabilities,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
        )
        for c in conditions
    )
    raw = {c.label: c for c in conditions}
    disc = _discriminativeness(
        built, raw=raw, seed=seed, n_resamples=n_resamples, alpha=alpha
    )
    return ValidationReport(
        k=k,
        expected_n_tasks=expected_n_tasks,
        seed=seed,
        conditions=built,
        discriminativeness=disc,
    )


def _ci_str(ci: BootstrapCI | None) -> str:
    if ci is None:
        return "—"
    return f"{ci.point:.3f} [{ci.lo:.3f}, {ci.hi:.3f}]"


def render_markdown(report: ValidationReport) -> str:
    lines = [
        "# Validation report — v2 live validation",
        "",
        f"- Dataset: `workspace_tool_use_v2` · n={report.expected_n_tasks} tasks "
        f"· k={report.k} · bootstrap seed={report.seed}",
        "- Temperature 0.0 was *requested*; no seed is sent and hosted providers "
        "are not greedy-deterministic at temp 0, so residual run-to-run variation "
        "is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob "
        "is the bootstrap RNG.",
        "",
        "## Per-condition reliability",
        "",
        "| condition | status | tasks | pass@1 | pass^3 [95% CI] |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            lines.append(
                f"| {c.label} | blocked | 0 | — | — (reason: {c.blocked_reason}) |"
            )
        else:
            p1 = "—" if c.pass_at_1 is None else f"{c.pass_at_1:.3f}"
            ci_s = _ci_str(c.pass_pow_k)
            lines.append(f"| {c.label} | {c.status} | {c.n_tasks} | {p1} | {ci_s} |")
    lines += [
        "",
        "## Per-tier pass^3 (accuracy curve)",
        "",
        "| condition | " + " | ".join(TIER_ORDER) + " |",
        "| --- | " + " | ".join("---" for _ in TIER_ORDER) + " |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        cells = [
            f"{c.pass_pow_k_by_tier[t]:.3f}" if t in c.pass_pow_k_by_tier else "—"
            for t in TIER_ORDER
        ]
        lines.append(f"| {c.label} | " + " | ".join(cells) + " |")
    lines += ["", "## Failure taxonomy × tier × capability", ""]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        lines += [
            f"### {c.label}",
            "",
            "| category | tier | capability | count |",
            "| --- | --- | --- | --- |",
        ]
        if not c.failure_taxonomy:
            lines.append("| (no failures) | — | — | 0 |")
        else:
            for (cat, tier, cap), n in sorted(
                c.failure_taxonomy.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                lines.append(f"| {cat} | {tier} | {cap} | {n} |")
        lines.append("")
    lines += ["## Deterministic vs flaky split", ""]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        det = ", ".join(c.deterministic_failures) or "none"
        flk = ", ".join(c.flaky_tasks) or "none"
        lines += [
            f"- **{c.label}** — Deterministic failures (all-3-fail): {det}",
            f"  - Flaky (mixed pass/fail across k): {flk}",
        ]
    lines += [
        "",
        "## Per-task pass matrix (task → reliable on each condition)",
        "",
        "| task | "
        + " | ".join(c.label for c in report.conditions if c.status != "blocked")
        + " |",
        "| --- | "
        + " | ".join("---" for c in report.conditions if c.status != "blocked")
        + " |",
    ]
    all_tasks = sorted({t for c in report.conditions for t in c.pass_matrix})
    for t in all_tasks:
        cells = []
        for c in report.conditions:
            if c.status == "blocked":
                continue
            if t not in c.pass_matrix:
                cells.append("·")
            else:
                cells.append("PASS" if c.pass_matrix[t] else "fail")
        lines.append(f"| {t} | " + " | ".join(cells) + " |")
    d = report.discriminativeness
    lines += [
        "",
        "## Discriminativeness verdict",
        "",
        f"- Rung met: **{d.rung}** (weak={d.weak_met}, strong={d.strong_met})",
        f"- {d.detail}",
    ]
    if d.strong_pair is not None:
        lines.append(
            f"- Separated hosted pair: {d.strong_pair[0]} vs {d.strong_pair[1]} "
            f"— Δ pass^3 {_ci_str(d.strong_pair_ci)} (CI excludes 0)."
        )
    if d.monotone_conditions:
        mc = ", ".join(d.monotone_conditions)
        lines.append(f"- Monotone tier gradient (T1≥T2≥T3≥T4): {mc}.")
    lines.append(
        "- n=50 honesty: with near-ceiling rates and 50 tasks the intervals are "
        "wide; absence of a detectable separation is not evidence of no separation."
    )
    return "\n".join(lines) + "\n"
