"""Pure final evaluation report (item 004 exit gate): build + render, no I/O.

Inputs: per-condition RunResult sequences loaded from committed runs JSONLs at
the edge, the tier sidecar, a capability map, the prices snapshot, and the
verbatim v1/v2 context text. Output: per-condition pass@1 / pass^k with seeded
cluster-bootstrap-by-task CIs, per-tier and per-capability pass^k, the fc-v2
task/agent/harness classification tables with deterministic exemplars, the
task-defect review queue, cost/latency from recorded usage, the Weeks 3-4
mechanical discriminativeness rule (shared by import from reports/validation —
the metrics/reliability `_percentile` precedent: import, don't extract, so the
frozen validation render cannot drift), pinned limitations, and roadmap
takeaways. No generation timestamp anywhere (grill Q5): time-like values
render only as recorded data, so build+render is a pure function of inputs.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from agent_eval_lab.metrics.agreement import BootstrapCI
from agent_eval_lab.metrics.cost import TokenPrice, total_cost_usd
from agent_eval_lab.metrics.reliability import (
    mean_latency_s,
    pass_at_1,
    pass_pow_k,
    pass_pow_k_bootstrap_ci,
    pass_pow_k_by_tier,
    token_totals,
)
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.reports.classify import (
    CLASSIFIER_VERSION,
    RunClassification,
    classify_run,
)
from agent_eval_lab.reports.validation import (
    TIER_ORDER,
    ConditionInput,
    Discriminativeness,
    _build_condition,
    _ci_str,
    _discriminativeness,
    _run_counts,
)

# Pinned by spec (criterion 16 section 12): excluded, not retried.
EXCLUDED_CONDITIONS: tuple[tuple[str, str], ...] = (
    (
        "openrouter:openai/gpt-5.5",
        "unreachable by network policy: direct access is region-blocked from "
        "this network and the datacenter-IP proxy route is ToS-blocked "
        "(docs/ROADMAP.md) — a network constraint, not a harness fault",
    ),
)


@dataclass(frozen=True, kw_only=True)
class FinalConditionInput:
    label: str
    condition_id: str | None  # None only when blocked with no records
    results: Sequence[RunResult] = field(default_factory=tuple)
    hosted: bool = False
    blocked_reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class ClassifiedExemplar:
    category: str
    subcategory: str
    task_id: str
    run_index: int
    detail: str


@dataclass(frozen=True, kw_only=True)
class FinalConditionReport:
    label: str
    condition_id: str | None
    hosted: bool
    status: str  # "complete" | "incomplete" | "blocked"
    n_tasks: int
    n_runs: int
    blocked_reason: str | None
    pass_at_1: float | None
    pass_pow_k: BootstrapCI | None
    pass_pow_k_by_tier: Mapping[str, float]
    pass_pow_k_by_capability: Mapping[str, float]
    classification_counts: Mapping[tuple[str, str], int]
    exemplars: tuple[ClassifiedExemplar, ...]
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float | None
    mean_latency_s: float | None
    incomplete_task_ids: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TaskDefectCandidate:
    task_id: str
    n_conditions: int  # non-blocked conditions WITH records for the task
    n_runs: int  # total recorded runs over those conditions


@dataclass(frozen=True, kw_only=True)
class FinalReport:
    dataset_id: str
    k: int
    expected_n_tasks: int
    seed: int
    classifier_version: str
    prices_snapshot_date: str | None
    context_text: str
    conditions: tuple[FinalConditionReport, ...]
    task_defect_candidates: tuple[TaskDefectCandidate, ...]
    discriminativeness: Discriminativeness
    excluded_conditions: tuple[tuple[str, str], ...]


def _pass_pow_k_by_capability(
    results: Sequence[RunResult], capabilities: Mapping[str, str]
) -> dict[str, float]:
    by_capability: dict[str, list[RunResult]] = {}
    for run in results:
        capability = capabilities.get(run.task_id)
        if capability is None:
            raise ValueError(
                f"task {run.task_id!r} has no capability in the capability map"
            )
        by_capability.setdefault(capability, []).append(run)
    return {
        capability: pass_pow_k(runs)
        for capability, runs in sorted(by_capability.items())
    }


def _classified_failures(
    results: Sequence[RunResult],
) -> tuple[tuple[RunResult, RunClassification], ...]:
    return tuple((run, classify_run(run)) for run in results if not run.grade.passed)


def _classification_counts(
    classified: Sequence[tuple[RunResult, RunClassification]],
) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for _, classification in classified:
        key = (classification.category, classification.subcategory or "—")
        counts[key] = counts.get(key, 0) + 1
    return counts


def _exemplars(
    classified: Sequence[tuple[RunResult, RunClassification]],
) -> tuple[ClassifiedExemplar, ...]:
    """One exemplar per category: lex-first task id, lowest run_index."""
    first: dict[str, tuple[RunResult, RunClassification]] = {}
    ordered = sorted(classified, key=lambda pair: (pair[0].task_id, pair[0].run_index))
    for run, classification in ordered:
        first.setdefault(classification.category, (run, classification))
    return tuple(
        ClassifiedExemplar(
            category=category,
            subcategory=first[category][1].subcategory or "—",
            task_id=first[category][0].task_id,
            run_index=first[category][0].run_index,
            detail=first[category][1].detail,
        )
        for category in sorted(first)
    )


def _blocked_condition(cond: FinalConditionInput) -> FinalConditionReport:
    return FinalConditionReport(
        label=cond.label,
        condition_id=cond.condition_id,
        hosted=cond.hosted,
        status="blocked",
        n_tasks=0,
        n_runs=0,
        blocked_reason=cond.blocked_reason or "no reachable records",
        pass_at_1=None,
        pass_pow_k=None,
        pass_pow_k_by_tier={},
        pass_pow_k_by_capability={},
        classification_counts={},
        exemplars=(),
        prompt_tokens=0,
        completion_tokens=0,
        cost_usd=None,
        mean_latency_s=None,
        incomplete_task_ids=(),
    )


def _build_final_condition(
    cond: FinalConditionInput,
    *,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
    prices: Mapping[str, TokenPrice],
) -> FinalConditionReport:
    if cond.blocked_reason is not None or not cond.results:
        return _blocked_condition(cond)
    counts = _run_counts(cond.results)
    deficit_ids = tuple(sorted(tid for tid, n in counts.items() if n < k))
    deficit = set(deficit_ids)
    complete = tuple(r for r in cond.results if r.task_id not in deficit)
    n_tasks = len({r.task_id for r in complete})
    status = (
        "complete" if n_tasks == expected_n_tasks and not deficit_ids else "incomplete"
    )
    classified = _classified_failures(cond.results)
    price = prices.get(cond.condition_id) if cond.condition_id else None
    prompt_tokens, completion_tokens = token_totals(cond.results)
    return FinalConditionReport(
        label=cond.label,
        condition_id=cond.condition_id,
        hosted=cond.hosted,
        status=status,
        n_tasks=n_tasks,
        n_runs=len(cond.results),
        blocked_reason=None,
        pass_at_1=pass_at_1(cond.results),
        pass_pow_k=(
            pass_pow_k_bootstrap_ci(
                complete, n_resamples=n_resamples, seed=seed, alpha=alpha
            )
            if complete
            else None
        ),
        pass_pow_k_by_tier=pass_pow_k_by_tier(complete, tiers) if complete else {},
        pass_pow_k_by_capability=(
            _pass_pow_k_by_capability(complete, capabilities) if complete else {}
        ),
        classification_counts=_classification_counts(classified),
        exemplars=_exemplars(classified),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cost_usd=(
            total_cost_usd(cond.results, price=price) if price is not None else None
        ),
        mean_latency_s=mean_latency_s(cond.results),
        incomplete_task_ids=deficit_ids,
    )


def _task_defect_candidates(
    conditions: Sequence[FinalConditionInput],
) -> tuple[TaskDefectCandidate, ...]:
    """Tasks failing ALL recorded runs on EVERY non-blocked condition with
    records for them (grill Q10): a condition with no records for a task
    contributes nothing (vacuous); blocked conditions are excluded entirely.
    Flagged for human review, never auto-classified (ADR-0013)."""
    live = [c for c in conditions if c.blocked_reason is None and c.results]
    per_task: dict[str, dict[str, list[bool]]] = {}
    for cond in live:
        for run in cond.results:
            per_task.setdefault(run.task_id, {}).setdefault(cond.label, []).append(
                run.grade.passed
            )
    return tuple(
        TaskDefectCandidate(
            task_id=task_id,
            n_conditions=len(per_task[task_id]),
            n_runs=sum(len(passes) for passes in per_task[task_id].values()),
        )
        for task_id in sorted(per_task)
        if not any(any(passes) for passes in per_task[task_id].values())
    )


def _shared_discriminativeness(
    conditions: Sequence[FinalConditionInput],
    *,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> Discriminativeness:
    """The Weeks 3-4 mechanical rule, reused by import (criterion 17)."""
    val_inputs = tuple(
        ConditionInput(
            label=c.label,
            results=tuple(c.results),
            hosted=c.hosted,
            blocked_reason=c.blocked_reason,
        )
        for c in conditions
    )
    built = tuple(
        _build_condition(
            ci,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
        )
        for ci in val_inputs
    )
    return _discriminativeness(
        built,
        raw={c.label: c for c in val_inputs},
        seed=seed,
        n_resamples=n_resamples,
        alpha=alpha,
    )


def build_final_report(
    *,
    conditions: Sequence[FinalConditionInput],
    dataset_id: str,
    tiers: Mapping[str, str],
    capabilities: Mapping[str, str],
    k: int,
    expected_n_tasks: int,
    seed: int,
    n_resamples: int,
    alpha: float,
    prices: Mapping[str, TokenPrice],
    prices_snapshot_date: str | None,
    context_text: str,
) -> FinalReport:
    built = tuple(
        _build_final_condition(
            c,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
            prices=prices,
        )
        for c in conditions
    )
    return FinalReport(
        dataset_id=dataset_id,
        k=k,
        expected_n_tasks=expected_n_tasks,
        seed=seed,
        classifier_version=CLASSIFIER_VERSION,
        prices_snapshot_date=prices_snapshot_date,
        context_text=context_text,
        conditions=built,
        task_defect_candidates=_task_defect_candidates(conditions),
        discriminativeness=_shared_discriminativeness(
            conditions,
            tiers=tiers,
            capabilities=capabilities,
            k=k,
            expected_n_tasks=expected_n_tasks,
            seed=seed,
            n_resamples=n_resamples,
            alpha=alpha,
        ),
        excluded_conditions=EXCLUDED_CONDITIONS,
    )


# ── Renderer (criterion 16's twelve sections, in order, plus the footer) ─────

_CLASSIFICATION_FOOTNOTES = (
    "`tree_collision` → agent_failure: oracle paths are disjoint from every "
    "initial-tree path (ADR-0012's conformance contract) and code-world has no "
    "delete tool, so a canonical-prefix collision can only be minted by the "
    "run's own write; exact-path equality is displacement, never collision "
    "(ADR-0010). Conditional on the conformance contract, which holds for the "
    "code-repair lineage.",
    "`oracle_empty` → task_failure: conformance proves every shipped oracle "
    "collects ≥1 test and the overlay always contributes the oracle files (a "
    "collection-breaking agent write yields suite status `error`, pytest exit "
    "2, never `no_tests`), so an empty oracle at grading time indicts the "
    "task data.",
    "`missing_final_state` → harness_failure: the runner always seeds "
    "final_state from initial_state, so its absence is a wiring defect.",
    "`step_exhaustion` outranks the oracle statuses: a budget-truncated "
    "attempt's red oracle is an artifact of the truncation, and the budget is "
    "data-validated (per-task metadata.max_steps via effective_max_steps, "
    "conformance-floored) — exhaustion is the agent's spend, not harness "
    "starvation.",
    "`malformed_reply` stays agent-side: message-level emptiness (assistant "
    "message with neither content nor tool_calls) means the provider envelope "
    "was well-formed and the model's own message was unparseable; only the "
    "empty-choices envelope (`provider_response`) is the harness's.",
    "`foreign_verdict` is the error-branch fallback: the evidence kind is an "
    "open string, so any unrecognized kind files as a harness verdict-plumbing "
    "fault, never an agent miss (grill Q1).",
)

_PINNED_LIMITATIONS = (
    "ADR-0010 residual trust boundary: the oracle suite imports agent-authored "
    "modules in-process, so import-time code in graded modules runs inside the "
    "sandbox process.",
    "Sandbox isolation is temp-dir-and-convention, not kernel-level: no "
    "containers, no per-test process isolation (001/002 non-goals).",
    "n=15 tasks, dev split only: intervals are wide and per-tier / "
    "per-capability cells are tiny.",
    "graders/policy.py dotted-path false-allow residual: an agent minting a "
    "fresh extension path at run time (e.g. writing `app.py.bak` under an "
    "`app.py` allowlist) is silently *passed* — a missed-detection bias the "
    "per-run classifier cannot see (003-spec criterion 16).",
    "pytest_edge cleanup is `shutil.rmtree(ignore_errors=True)`, so a sandbox "
    "dir can leak silently; a disk-full OSError mid-materialize is captured as "
    'an ExecutionError(kind="harness") by the oracle edge — the worked '
    "example of a `sandbox_fault` harness failure (001-review).",
    "Hosted providers are not greedy-deterministic at temperature 0; "
    "run-to-run variation is measured by k=3 + pass^3, never claimed away.",
    "`openrouter:gpt-5.5` is unreachable from this network (region / "
    "datacenter-IP ToS policy) — a network constraint, not a harness fault.",
)

_ROADMAP_TAKEAWAYS = (
    "The fc-v2 (category, subcategory) counts are the direct input to the "
    "Weeks 9-10 failure-mining work; downstream joins on "
    "(classifier_version, category, subcategory) (ADR-0013).",
    "Task-defect candidates are review-queue input, never auto-reclassified; "
    "an adjudicated defect ships as a future dataset version, never an edit "
    "(append-only).",
    "The per-tier and per-capability gradients feed the Weeks 9-10 hardness "
    "levers recorded in the Weeks 3-4 takeaways.",
    "The committed runs JSONLs embed agent solution trees and oracle output, "
    "so they join the Weeks 9-10 never-train manifest beside the "
    "review-fixtures sidecar.",
)

_RUN_DIR = "docs/2026-06-11-coding-agent-eval"
_REGEN_RUNS = (
    ("C1", "deepseek:deepseek-v4-pro", "runs-deepseek-deepseek-v4-pro.jsonl"),
    ("C2", "glm:Pro/zai-org/GLM-5.1", "runs-glm-Pro-zai-org-GLM-5.1.jsonl"),
    ("C3", "minimax:MiniMax-M3", "runs-minimax-MiniMax-M3.jsonl"),
    ("C4", "local:Qwen/Qwen3-8B", "runs-local-Qwen-Qwen3-8B.jsonl"),
)
# Static text by spec (criterion 16): the canonical regeneration command over
# the committed artifact paths — never derived from this build's inputs.
_REGENERATION_COMMAND = "\n".join(
    (
        "uv run python -m agent_eval_lab.cli report-final \\",
        "  --runs \\",
        *(
            f"    {label}={condition}={_RUN_DIR}/runs/{filename} \\"
            for label, condition, filename in _REGEN_RUNS
        ),
        "  --dataset examples/datasets/code_repair_v1.jsonl \\",
        "  --tiers examples/datasets/code_repair_v1_tiers.json \\",
        f"  --prices {_RUN_DIR}/prices.json \\",
        f"  --context-file {_RUN_DIR}/v2-context.md \\",
        "  --k 3 --expected-n-tasks 15 --seed 20260610 "
        "--n-resamples 2000 --alpha 0.05 \\",
        f"  --out {_RUN_DIR}/final-evaluation-report.md",
    )
)


def _fmt(value: float | None) -> str:
    return "—" if value is None else f"{value:.3f}"


def _header_lines(report: FinalReport) -> list[str]:
    condition_cells = ", ".join(
        f"{c.label}={c.condition_id or 'unknown'} "
        f"({'hosted' if c.hosted else 'local'}, {c.status})"
        for c in report.conditions
    )
    return [
        "# Final evaluation report — coding-agent-eval (Weeks 5-6)",
        "",
        f"- Dataset: `{report.dataset_id}` · n={report.expected_n_tasks} tasks "
        f"· k={report.k} · bootstrap seed={report.seed} "
        f"· classifier {report.classifier_version}",
        f"- Conditions: {condition_cells}",
        "- Temperature 0.0 was *requested*; no seed is sent and hosted providers "
        "are not greedy-deterministic at temp 0, so residual run-to-run variation "
        "is exactly what k=3 + pass^3 measures. The only seeded, reproducible knob "
        "is the bootstrap RNG.",
        "",
    ]


def _reliability_lines(report: FinalReport) -> list[str]:
    lines = [
        "## Per-condition reliability",
        "",
        "| condition | status | tasks | runs | pass@1 | pass^3 [95% CI] |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            lines.append(
                f"| {c.label} | blocked | 0 | 0 | — | — (reason: {c.blocked_reason}) |"
            )
        else:
            lines.append(
                f"| {c.label} | {c.status} | {c.n_tasks} | {c.n_runs} "
                f"| {_fmt(c.pass_at_1)} | {_ci_str(c.pass_pow_k)} |"
            )
    for c in report.conditions:
        if c.status == "blocked" or not c.incomplete_task_ids:
            continue
        ids = ", ".join(c.incomplete_task_ids)
        lines.append(
            f"  - {c.label}: excluded (incomplete, <k runs): "
            f"{len(c.incomplete_task_ids)} — {ids} "
            f"(pass@1 over observed runs; excluded from pass^k)"
        )
    return lines + [""]


def _axis_table_lines(
    report: FinalReport, *, title: str, axis: str, columns: tuple[str, ...]
) -> list[str]:
    lines = [
        title,
        "",
        "| condition | " + " | ".join(columns) + " |",
        "| --- | " + " | ".join("---" for _ in columns) + " |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        values = getattr(c, axis)
        cells = [f"{values[col]:.3f}" if col in values else "—" for col in columns]
        lines.append(f"| {c.label} | " + " | ".join(cells) + " |")
    return lines + [""]


def _classification_lines(report: FinalReport) -> list[str]:
    lines = [
        f"## Failure classification ({report.classifier_version})",
        "",
        "Derived at report time from the recorded mechanical discriminators; "
        "never stored on any record (ADR-0013).",
        "",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        lines += [
            f"### {c.label} ({c.condition_id})",
            "",
            "| category | subcategory | count |",
            "| --- | --- | --- |",
        ]
        if not c.classification_counts:
            lines.append("| (no failures) | — | 0 |")
        else:
            for (category, subcategory), n in sorted(
                c.classification_counts.items(), key=lambda kv: (-kv[1], kv[0])
            ):
                lines.append(f"| {category} | {subcategory} | {n} |")
        lines.append("")
        if c.exemplars:
            lines.append(
                "Exemplars (deterministic: lex-first task id, lowest run_index):"
            )
            lines += [
                f"- **{e.category}/{e.subcategory}** — task `{e.task_id}`, "
                f"run {e.run_index}: {e.detail}"
                for e in c.exemplars
            ]
            lines.append("")
    lines += ["Judgment-row footnotes:", ""]
    lines += [f"- {note}" for note in _CLASSIFICATION_FOOTNOTES]
    return lines + [""]


def _defect_queue_lines(report: FinalReport) -> list[str]:
    lines = [
        "## Task-defect candidates",
        "",
        "Task ids failing all recorded runs on every non-blocked condition with "
        "records for them — *flagged for human review*, never auto-classified: "
        "conformance already proves solvability, oracle breadth, and symptom "
        'reality, so unanimity defaults to "hard, not defective" pending '
        "adjudication.",
        "",
    ]
    if not report.task_defect_candidates:
        lines.append("none")
    else:
        lines += [
            "| task | conditions with records | total runs (all failing) |",
            "| --- | --- | --- |",
        ]
        lines += [
            f"| {c.task_id} | {c.n_conditions} | {c.n_runs} |"
            for c in report.task_defect_candidates
        ]
    return lines + [""]


def _cost_lines(report: FinalReport) -> list[str]:
    snapshot = report.prices_snapshot_date or "unspecified"
    lines = [
        "## Cost and latency",
        "",
        f"Prices snapshot: {snapshot} (committed prices.json); conditions "
        "absent from the snapshot render as not computed. Latency is summed "
        "from recorded per-run `usage.latency_s`.",
        "",
        "| condition | prompt tokens | completion tokens | cost (USD) "
        "| mean run latency (s) |",
        "| --- | --- | --- | --- | --- |",
    ]
    for c in report.conditions:
        if c.status == "blocked":
            continue
        cost = "not computed" if c.cost_usd is None else f"{c.cost_usd:.4f}"
        latency = "—" if c.mean_latency_s is None else f"{c.mean_latency_s:.2f}"
        lines.append(
            f"| {c.label} | {c.prompt_tokens} | {c.completion_tokens} "
            f"| {cost} | {latency} |"
        )
    return lines + [""]


def _context_lines(report: FinalReport) -> list[str]:
    return [
        "## Context: prior baselines (workspace_tool_use v1/v2)",
        "",
        report.context_text.rstrip("\n"),
        "",
        "Cross-dataset numbers are *context*, never a paired statistic: the "
        "task universes differ, so no CI is computed across them.",
        "",
    ]


def _discriminativeness_lines(report: FinalReport) -> list[str]:
    d = report.discriminativeness
    lines = [
        "## Discriminativeness verdict",
        "",
        f"- Rung met: **{d.rung}** (weak={d.weak_met}, strong={d.strong_met}) — "
        "the Weeks 3-4 mechanical rule, reused unchanged.",
    ]
    if d.strong_pair is not None:
        lines.append(
            f"- Separated hosted pair: {d.strong_pair[0]} vs {d.strong_pair[1]} "
            f"— Δ pass^3 {_ci_str(d.strong_pair_ci)} (CI excludes 0)."
        )
    if d.monotone_conditions:
        names = ", ".join(d.monotone_conditions)
        lines.append(
            "- Non-trivial monotone tier gradient (T1≥T2≥T3≥T4 with ≥1 strict "
            f"decrease): {names}."
        )
    for a_label, b_label, ci in d.near_miss_pairs:
        if ci.point == 0.0 and ci.lo == 0.0 and ci.hi == 0.0:
            lines.append(
                f"- No observed difference: {a_label} vs {b_label} — both "
                f"conditions identical on this dataset (Δ {ci.point:.3f})."
            )
        else:
            lines.append(
                f"- Near-miss: {a_label} vs {b_label} — Δ pass^3 {_ci_str(ci)} "
                f"(CI touches 0; not decisive at n={report.expected_n_tasks})."
            )
    for a_label, b_label in d.skipped_pairs:
        lines.append(
            f"- Skipped pair: {a_label} vs {b_label} — universe mismatch "
            f"(task-id sets differ; paired CI requires identical universe)."
        )
    lines.append(
        f"- n={report.expected_n_tasks} honesty: intervals are wide; absence of "
        "a detectable separation is not evidence of no separation."
    )
    return lines + [""]


def _limitations_lines(report: FinalReport) -> list[str]:
    lines = ["## Known limitations", ""]
    lines += [f"- {limitation}" for limitation in _PINNED_LIMITATIONS]
    for c in report.conditions:
        if c.status == "blocked":
            condition_name = c.condition_id or "condition id unknown — no records"
            lines.append(
                f"- Condition {c.label} ({condition_name}) is blocked: "
                f"{c.blocked_reason}; its rows render as blocked and no "
                "numbers are fabricated."
            )
        elif c.status == "incomplete":
            lines.append(
                f"- Condition {c.label} is incomplete "
                f"({c.n_tasks}/{report.expected_n_tasks} tasks at full k); "
                "pass^k covers only its complete tasks."
            )
    return lines + [""]


def _excluded_lines(report: FinalReport) -> list[str]:
    lines = ["## Excluded conditions", ""]
    lines += [
        f"- `{condition_id}` — {reason}"
        for condition_id, reason in report.excluded_conditions
    ]
    return lines + [""]


def _footer_lines() -> list[str]:
    return [
        "---",
        "",
        "Regenerate byte-identically from the committed artifacts with:",
        "",
        "```",
        _REGENERATION_COMMAND,
        "```",
    ]


def render_markdown(report: FinalReport) -> str:
    capabilities = tuple(
        sorted(
            {
                capability
                for c in report.conditions
                for capability in c.pass_pow_k_by_capability
            }
        )
    )
    lines = (
        _header_lines(report)
        + _reliability_lines(report)
        + _axis_table_lines(
            report,
            title="## Per-tier pass^3",
            axis="pass_pow_k_by_tier",
            columns=TIER_ORDER,
        )
        + _axis_table_lines(
            report,
            title="## Per-capability pass^3",
            axis="pass_pow_k_by_capability",
            columns=capabilities,
        )
        + _classification_lines(report)
        + _defect_queue_lines(report)
        + _cost_lines(report)
        + _context_lines(report)
        + _discriminativeness_lines(report)
        + _limitations_lines(report)
        + ["## Roadmap takeaways", ""]
        + [f"- {takeaway}" for takeaway in _ROADMAP_TAKEAWAYS]
        + [""]
        + _excluded_lines(report)
        + _footer_lines()
    )
    return "\n".join(lines) + "\n"
