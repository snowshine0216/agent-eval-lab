"""Pure M1 report: build + render, no I/O (mirrors reports/final.py).

Per-domain ExperimentResults (CI-by-method), macro composites, per-domain Pareto
frontiers, fc-v3 taxonomy per condition, validity/invalid-rate + void/INCOMPLETE,
Holm-corrected planned comparisons, and provenance (spec_hash + snapshot hashes).
Partial coverage is first-class: a (condition, domain) with no runs contributes
no result and is listed in domains_not_run. Deterministic for fixed seed.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.experiments.aggregate import (
    EfficiencySummary,
    aggregate_domain_metric,
    efficiency_summary,
    macro_composite,
)
from agent_eval_lab.experiments.comparisons import (
    ComparisonRow,
    run_planned_comparisons,
)
from agent_eval_lab.experiments.pricing import PricingSnapshot, condition_cost_usd
from agent_eval_lab.experiments.schema import (
    Domain,
    ExperimentResult,
    ExperimentSpec,
    MetricDef,
)
from agent_eval_lab.metrics.pareto import ParetoPoint, pareto_frontier
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    classify_run,
)
from agent_eval_lab.reports.m1_detail import (
    CondDomainEfficiency,
    cond_domain_efficiency,
)
from agent_eval_lab.runners.multi_run import ReplacementOutcome

_DOMAINS: tuple[Domain, ...] = ("F", "D", "B")


@dataclass(frozen=True, kw_only=True)
class DomainEfficiency:
    condition_id: str
    domain: Domain
    summary: EfficiencySummary
    cost_usd: float | None


@dataclass(frozen=True, kw_only=True)
class ParetoChart:
    domain: Domain
    axis: str  # "cost_usd" | "rounds" | "tokens"
    frontier: tuple[ParetoPoint, ...]
    all_points: tuple[ParetoPoint, ...]


@dataclass(frozen=True, kw_only=True)
class ConditionFailureTaxonomy:
    condition_id: str
    counts: Mapping[tuple[str, str], int]


@dataclass(frozen=True, kw_only=True)
class ValidityRow:
    condition_id: str
    domain: Domain
    valid: int
    invalid: int
    invalid_rate: float
    void_task_count: int


@dataclass(frozen=True, kw_only=True)
class M1Report:
    experiment_id: str
    spec_hash: str
    dataset_snapshot_hash: str
    pricing_snapshot_hash: str
    pricing_snapshot_date: str
    k: int
    max_invalid_rate: float
    seed: int
    n_resamples: int
    alpha: float
    classifier_version: str
    macro_weights: Mapping[str, float]
    per_domain_results: tuple[ExperimentResult, ...]  # primary metric only
    composites: tuple[ExperimentResult, ...]
    efficiency: tuple[DomainEfficiency, ...]
    pareto_charts: tuple[ParetoChart, ...]
    failure_taxonomy: tuple[ConditionFailureTaxonomy, ...]
    validity: tuple[ValidityRow, ...]
    comparisons: tuple[ComparisonRow, ...]
    conditions_present: tuple[str, ...]
    domains_not_run: tuple[str, ...]
    cond_domain_efficiency_rollup: tuple[tuple[str, str, CondDomainEfficiency], ...]
    subreport_domains: tuple[str, ...]


def _primary_for(spec: ExperimentSpec, domain: Domain) -> MetricDef:
    for m in spec.metrics:
        if m.domain == domain and m.primary:
            return m
    raise ValueError(f"no primary metric for domain {domain}")


def _valid_runs(outcomes: Sequence[ReplacementOutcome]) -> list[RunResult]:
    runs: list[RunResult] = []
    for o in outcomes:
        if not o.void:
            runs.extend(o.valid_runs)
    return runs


def _classification_counts(runs: Sequence[RunResult]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for run in runs:
        if run.grade.passed:
            continue
        c: RunClassification = classify_run(run)
        key = (c.category, c.subcategory or "—")
        counts[key] = counts.get(key, 0) + 1
    return counts


def build_m1_report(
    *,
    spec: ExperimentSpec,
    outcomes_by_condition_domain: Mapping[
        str, Mapping[str, Sequence[ReplacementOutcome]]
    ],
    pricing: PricingSnapshot,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> M1Report:
    conditions_present = tuple(sorted(outcomes_by_condition_domain))
    per_domain: list[ExperimentResult] = []
    efficiency: list[DomainEfficiency] = []
    validity: list[ValidityRow] = []
    taxonomy: list[ConditionFailureTaxonomy] = []
    rollup: list[tuple[str, str, CondDomainEfficiency]] = []
    # valid-run map for comparisons / Pareto / fc-v3
    runs_by: dict[str, dict[str, list[RunResult]]] = {}
    domains_seen: set[str] = set()

    for cond in conditions_present:
        per_cond_runs: list[RunResult] = []
        runs_by[cond] = {}
        for domain in _DOMAINS:
            outcomes = tuple(outcomes_by_condition_domain[cond].get(domain, ()))
            if not outcomes:
                continue
            domains_seen.add(domain)
            primary = _primary_for(spec, domain)
            result = aggregate_domain_metric(
                outcomes=outcomes,
                metric=primary,
                condition_id=cond,
                experiment_id=spec.experiment_id,
                spec_hash=spec.spec_hash,
                seed=seed,
                n_resamples=n_resamples,
                alpha=alpha,
            )
            per_domain.append(result)
            valid = _valid_runs(outcomes)
            runs_by[cond][domain] = valid
            per_cond_runs.extend(valid)
            eff = efficiency_summary(outcomes=outcomes)
            cost = (
                condition_cost_usd(valid, cond, pricing)
                if cond in pricing.prices and valid
                else None
            )
            efficiency.append(
                DomainEfficiency(
                    condition_id=cond, domain=domain, summary=eff, cost_usd=cost
                )
            )
            rollup.append(
                (
                    cond,
                    domain,
                    cond_domain_efficiency(
                        runs=valid, condition_id=cond, pricing=pricing
                    ),
                )
            )
            invalid = result.invalid_run_count
            total = result.valid_run_count + invalid
            validity.append(
                ValidityRow(
                    condition_id=cond,
                    domain=domain,
                    valid=result.valid_run_count,
                    invalid=invalid,
                    invalid_rate=(invalid / total if total else 0.0),
                    void_task_count=sum(1 for o in outcomes if o.void),
                )
            )
        taxonomy.append(
            ConditionFailureTaxonomy(
                condition_id=cond, counts=_classification_counts(per_cond_runs)
            )
        )

    composites = tuple(
        macro_composite(
            per_domain_primary=[r for r in per_domain if r.condition_id == cond],
            weights=spec.macro_weights,
            condition_id=cond,
            experiment_id=spec.experiment_id,
            spec_hash=spec.spec_hash,
        )
        for cond in conditions_present
    )

    pareto_charts = tuple(
        _pareto_for(per_domain, efficiency, domain, axis)
        for domain in sorted(domains_seen)
        for axis in ("cost_usd", "rounds", "tokens")
    )

    comparisons = run_planned_comparisons(
        comparisons=spec.planned_comparisons,
        families=spec.families,
        runs_by_condition_domain=runs_by,
        seed=seed,
        n_resamples=n_resamples,
        alpha_default=alpha,
    )
    domains_not_run = tuple(d for d in _DOMAINS if d not in domains_seen)

    return M1Report(
        experiment_id=spec.experiment_id,
        spec_hash=spec.spec_hash,
        dataset_snapshot_hash=spec.dataset_snapshot_hash,
        pricing_snapshot_hash=spec.pricing_snapshot_hash,
        pricing_snapshot_date=pricing.snapshot_date,
        k=spec.k,
        max_invalid_rate=spec.max_invalid_rate,
        seed=seed,
        n_resamples=n_resamples,
        alpha=alpha,
        classifier_version=CLASSIFIER_VERSION,
        macro_weights={w.domain: w.weight for w in spec.macro_weights},
        per_domain_results=tuple(per_domain),
        composites=composites,
        efficiency=tuple(efficiency),
        pareto_charts=pareto_charts,
        failure_taxonomy=tuple(taxonomy),
        validity=tuple(validity),
        comparisons=comparisons,
        conditions_present=conditions_present,
        domains_not_run=domains_not_run,
        cond_domain_efficiency_rollup=tuple(rollup),
        subreport_domains=tuple(sorted(domains_seen)),
    )


def _pareto_for(
    per_domain: Sequence[ExperimentResult],
    efficiency: Sequence[DomainEfficiency],
    domain: str,
    axis: str,
) -> ParetoChart:
    success_of = {r.condition_id: r.estimate for r in per_domain if r.domain == domain}
    points: list[ParetoPoint] = []
    for eff in efficiency:
        if eff.domain != domain or eff.condition_id not in success_of:
            continue
        if axis == "cost_usd":
            cost = eff.cost_usd
            if cost is None:
                continue
        elif axis == "rounds":
            cost = eff.summary.median_rounds
        else:  # tokens
            cost = float(eff.summary.total_tokens)
        points.append(
            ParetoPoint(
                condition_id=eff.condition_id,
                success=success_of[eff.condition_id],
                cost=cost,
            )
        )
    return ParetoChart(
        domain=domain,
        axis=axis,
        frontier=pareto_frontier(tuple(points)),
        all_points=tuple(points),
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _ci_cell(r: ExperimentResult) -> str:
    if r.void and r.valid_run_count == 0:
        return "INCOMPLETE (VOID)"
    if r.ci_lower is None or r.ci_upper is None:
        base = f"{r.estimate:.3f} (no CI)"
    else:
        base = f"{r.estimate:.3f} [{r.ci_lower:.3f}, {r.ci_upper:.3f}]"
    return base + (" — VOID (incomplete tasks present)" if r.void else "")


def _per_domain_lines(report: M1Report) -> list[str]:
    lines = [
        "## Per-domain scores (primary metric: pass^k)",
        "",
        "| condition | domain | pass^k [95% CI] | CI method | valid | invalid |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.per_domain_results:
        lines.append(
            f"| {r.condition_id} | {r.domain} | {_ci_cell(r)} | {r.ci_method} "
            f"| {r.valid_run_count} | {r.invalid_run_count} |"
        )
    if report.domains_not_run:
        for d in report.domains_not_run:
            lines.append(f"| (all conditions) | {d} | not yet run | — | 0 | 0 |")
    return lines + [""]


def _composite_lines(report: M1Report) -> list[str]:
    weights = ", ".join(f"{d}={w}" for d, w in sorted(report.macro_weights.items()))
    lines = [
        "## Macro composite",
        "",
        f"Equal-weighted mean of per-domain primary estimates (weights: {weights}); "
        "weighted by DOMAIN, never a raw task pool (D23). CI method: "
        "`weighted_halfwidth_propagation` (conservative half-width propagation under "
        "independence; the composite over K=3 domains has no defensible bootstrap CI).",
        "",
        "| condition | composite | note |",
        "| --- | --- | --- |",
    ]
    for c in report.composites:
        note = (
            "reduced coverage (some domains not run / void)"
            if c.void
            else "all domains present"
        )
        ci = (
            f" [{c.ci_lower:.3f}, {c.ci_upper:.3f}]"
            if c.ci_lower is not None and c.ci_upper is not None
            else ""
        )
        lines.append(f"| {c.condition_id} | {c.estimate:.3f}{ci} | {note} |")
    if report.domains_not_run:
        lines.append("")
        lines.append(
            f"> Composite computed over present domains only; not yet run: "
            f"{', '.join(report.domains_not_run)}."
        )
    return lines + [""]


def _pareto_lines(report: M1Report) -> list[str]:
    lines = ["## Pareto frontiers (success vs efficiency, per domain)", ""]
    if not report.pareto_charts:
        return lines + ["(no domains run)", ""]
    for chart in report.pareto_charts:
        lines += [
            f"### {chart.domain} — pass^k vs {chart.axis}",
            "",
            "| condition | pass^k | " + chart.axis + " | on frontier |",
            "| --- | --- | --- | --- |",
        ]
        frontier_ids = {p.condition_id for p in chart.frontier}
        for p in sorted(chart.all_points, key=lambda x: (x.cost, -x.success)):
            mark = "yes" if p.condition_id in frontier_ids else "—"
            lines.append(
                f"| {p.condition_id} | {p.success:.3f} | {p.cost:.4g} | {mark} |"
            )
        lines.append("")
    return lines


def _taxonomy_lines(report: M1Report) -> list[str]:
    lines = [
        f"## Failure classification ({report.classifier_version}) per condition",
        "",
    ]
    for t in report.failure_taxonomy:
        lines += [
            f"### {t.condition_id}",
            "",
            "| category | subcategory | count |",
            "| --- | --- | --- |",
        ]
        if not t.counts:
            lines.append("| (no failures) | — | 0 |")
        else:
            for (cat, sub), n in sorted(
                t.counts.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                lines.append(f"| {cat} | {sub} | {n} |")
        lines.append("")
    return lines


def _validity_lines(report: M1Report) -> list[str]:
    lines = [
        "## Validity mask / invalid-rate / void",
        "",
        f"Max invalid-rate (VOID threshold): {report.max_invalid_rate:.2f}; "
        f"k={report.k} valid trials required per task (D34). A task that voids before "
        "k valid trials is INCOMPLETE and excluded from pass^k — never scored over <k.",
        "",
        "| condition | domain | valid | invalid | invalid-rate | void tasks |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for v in report.validity:
        flag = " over threshold" if v.invalid_rate > report.max_invalid_rate else ""
        lines.append(
            f"| {v.condition_id} | {v.domain} | {v.valid} | {v.invalid} "
            f"| {v.invalid_rate:.3f}{flag} | {v.void_task_count} |"
        )
    return lines + [""]


def _comparison_lines(report: M1Report) -> list[str]:
    lines = [
        "## Planned comparisons"
        " (Holm-corrected, two-sided; effect = metric(b) − metric(a))",
        "",
        "| comparison | domain | Δ pass^k [CI] | p | Holm-adj p | rejected |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.comparisons:
        if c.skipped or c.decision is None:
            lines.append(
                f"| {c.comparison_name} | {c.domain}"
                " | (skipped — arm not run) | — | — | — |"
            )
            continue
        ci = (
            f"{c.delta_point:+.3f} [{c.ci_lower:+.3f}, {c.ci_upper:+.3f}]"
            if c.ci_lower is not None
            else f"{c.delta_point:+.3f}"
        )
        lines.append(
            f"| {c.comparison_name} | {c.domain} | {ci} | {c.decision.p:.4f} "
            f"| {c.decision.adjusted_p:.4f} "
            f"| {'yes' if c.decision.rejected else 'no'} |"
        )
    return lines + [""]


def _header_lines(report: M1Report) -> list[str]:
    return [
        f"# M1 model characterization report — {report.experiment_id}",
        "",
        f"- spec_hash: `{report.spec_hash}` · dataset_snapshot_hash: "
        f"`{report.dataset_snapshot_hash}` · pricing_snapshot_hash: "
        f"`{report.pricing_snapshot_hash}` (snapshot {report.pricing_snapshot_date})",
        f"- k={report.k} valid trials · bootstrap seed={report.seed} "
        f"· n_resamples={report.n_resamples} · alpha={report.alpha} "
        f"· classifier {report.classifier_version}",
        f"- conditions present: {', '.join(report.conditions_present) or '(none)'}",
        (
            f"- domains not yet run: {', '.join(report.domains_not_run)} "
            "(rendered as 'not yet run', not as failures)"
            if report.domains_not_run
            else "- all domains (F/D/B) present"
        ),
        "",
    ]


def _efficiency_rollup_lines(report: M1Report) -> list[str]:
    lines = [
        "## Efficiency & cost",
        "",
        "Per (condition, domain). Rounds are time-to-completion (right-censored "
        "for budget-capped runs); tokens and cost are observed over ALL valid "
        "runs incl. capped (never censored).",
        "",
        "| condition | domain | rounds median [min–max] | prompt tok | "
        "completion tok | total tok | cost (USD) | tool calls | safety-cap hits "
        "| max-rounds hits | dominant stop |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cond, domain, eff in report.cond_domain_efficiency_rollup:
        rounds = f"{eff.rounds_median:g} [{eff.rounds_min}–{eff.rounds_max}]"
        if eff.censored_count > 0:
            bound = "cap" if eff.cap_bound is None else f"cap {eff.cap_bound}"
            rounds += f" ({eff.censored_count} right-censored at {bound})"
        cost = "—" if eff.cost_usd is None else f"{eff.cost_usd:.4f}"
        total_tools = sum(eff.tool_call_totals.values())
        dominant = (
            max(
                eff.stop_reason_counts,
                key=lambda sr: (eff.stop_reason_counts[sr], sr),
            )
            if eff.stop_reason_counts
            else "—"
        )
        lines.append(
            f"| {cond} | {domain} | {rounds} | {eff.prompt_tokens} "
            f"| {eff.completion_tokens} | {eff.total_tokens} | {cost} "
            f"| {total_tools} | {eff.safety_cap_hits} | {eff.max_rounds_hits} "
            f"| {dominant} |"
        )
    return lines + [""]


def _headline_lines(report: M1Report) -> list[str]:
    lines = ["## Per-domain headlines", ""]
    domains = sorted({r.domain for r in report.per_domain_results})
    for domain in domains:
        rows = [r for r in report.per_domain_results if r.domain == domain]
        best = max(rows, key=lambda r: r.estimate)
        cheapest = None
        frontier_cost = None
        for chart in report.pareto_charts:
            if chart.domain == domain and chart.axis == "cost_usd":
                for p in chart.frontier:
                    if frontier_cost is None or p.cost < frontier_cost:
                        frontier_cost, cheapest = p.cost, p.condition_id
        cheap_txt = cheapest or "—"
        lines.append(
            f"- **{domain}** — best pass^k: `{best.condition_id}` "
            f"({best.estimate:.3f}); cheapest on cost-frontier: `{cheap_txt}`"
        )
    return lines + [""]


def _subreport_lines(report: M1Report) -> list[str]:
    lines = ["## Subreports", ""]
    for domain in report.subreport_domains:
        lines.append(f"- [`M1-{domain}-report.md`](M1-{domain}-report.md)")
    # Hand-authored companions (never generated, never overwritten — spec §2/§7)
    lines += [
        "- [`M1-F-failure-analysis.md`](M1-F-failure-analysis.md) "
        "(hand-authored companion)",
        "- [`M1-F-report-NOTES.md`](M1-F-report-NOTES.md) (hand-authored companion)",
    ]
    return lines + [""]


def render_markdown(report: M1Report) -> str:
    lines = (
        _header_lines(report)
        + _per_domain_lines(report)
        + _headline_lines(report)
        + _composite_lines(report)
        + _efficiency_rollup_lines(report)
        + _pareto_lines(report)
        + _comparison_lines(report)
        + _taxonomy_lines(report)
        + _validity_lines(report)
        + _subreport_lines(report)
    )
    return "\n".join(lines) + "\n"
