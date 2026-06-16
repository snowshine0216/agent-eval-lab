"""Pure M1 per-domain detail report: build + render, no I/O (mirrors m1.py).

Derives per-task / per-condition pass matrices, grader-aware failure gaps
(evidence_summary), edit signals (edit_paths), task-defect candidates (defects),
fc-v4 classification per task×condition (classify), and a rich per-(condition,
domain) efficiency rollup (CondDomainEfficiency). Every derived value is a pure
function of records + spec + pricing; all iteration is over sorted keys, so the
render is deterministic (byte-identical for fixed input). REPORT-LAYER ONLY: no
runner, no scoring, no pass^k math.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import median

from agent_eval_lab.experiments.pricing import PricingSnapshot, condition_cost_usd
from agent_eval_lab.experiments.schema import ExperimentSpec
from agent_eval_lab.records.grade import RunResult
from agent_eval_lab.reports.classify import classify_run
from agent_eval_lab.reports.defects import (
    DefectInputGroup,
    TaskDefectCandidate,
    task_defect_candidates,
)
from agent_eval_lab.reports.edit_paths import EditPaths, edit_paths
from agent_eval_lab.reports.evidence_summary import EvidenceGap, evidence_gap
from agent_eval_lab.runners.multi_run import ReplacementOutcome


@dataclass(frozen=True, kw_only=True)
class CondDomainEfficiency:
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int
    cap_bound: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int
    max_rounds_hits: int
    stop_reason_counts: Mapping[str, int]


def _is_censored(run: RunResult) -> bool:
    return run.trajectory.safety_cap_bound or run.trajectory.max_rounds_bound


def _cap_bound_of(run: RunResult) -> int | None:
    t = run.trajectory
    if t.max_rounds_bound:
        return t.max_rounds
    if t.safety_cap_bound:
        return t.safety_cap
    return None


def _counts(values: Sequence[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in sorted(values):
        out[v] = out.get(v, 0) + 1
    return out


def cond_domain_efficiency(
    *,
    runs: Sequence[RunResult],
    condition_id: str,
    pricing: PricingSnapshot,
) -> CondDomainEfficiency:
    if not runs:
        return CondDomainEfficiency(
            rounds_median=0.0,
            rounds_min=0,
            rounds_max=0,
            censored_count=0,
            cap_bound=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=None,
            tool_call_totals={},
            safety_cap_hits=0,
            max_rounds_hits=0,
            stop_reason_counts={},
        )
    rounds = [r.trajectory.rounds for r in runs]
    censored = [r for r in runs if _is_censored(r)]
    cap_bound = _cap_bound_of(censored[0]) if censored else None
    prompt = sum(r.trajectory.usage.prompt_tokens for r in runs)
    completion = sum(r.trajectory.usage.completion_tokens for r in runs)
    tool_totals: dict[str, int] = {}
    for r in runs:
        for tool in sorted(r.trajectory.tool_call_counts):
            n = r.trajectory.tool_call_counts[tool]
            tool_totals[tool] = tool_totals.get(tool, 0) + n
    stop_counts = _counts([r.trajectory.stop_reason for r in runs])
    cost = (
        condition_cost_usd(runs, condition_id, pricing)
        if condition_id in pricing.prices
        else None
    )
    return CondDomainEfficiency(
        rounds_median=median(rounds),
        rounds_min=min(rounds),
        rounds_max=max(rounds),
        censored_count=len(censored),
        cap_bound=cap_bound,
        prompt_tokens=prompt,
        completion_tokens=completion,
        total_tokens=prompt + completion,
        cost_usd=cost,
        tool_call_totals=tool_totals,
        safety_cap_hits=stop_counts.get("safety_cap", 0),
        max_rounds_hits=stop_counts.get("max_rounds", 0),
        stop_reason_counts=stop_counts,
    )


# ---------------------------------------------------------------------------
# Per-domain detail value objects
# ---------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class TaskConditionCell:
    condition_id: str
    present: bool  # False -> render "—" row (spec §6: condition missing a task)
    valid_trials: int  # len(valid_runs) for this (task, cond)
    passed_trials: int  # #valid runs with grade.passed
    incomplete: bool  # valid_trials < k (spec §6 void/incomplete; D34)
    per_trial: tuple[bool, ...]  # the ✅❌ string source, record order over valid runs
    dominant_stop_reason: str  # most common stop_reason over valid runs ("—" if none)
    rounds_median: float
    rounds_min: int
    rounds_max: int
    censored_count: int
    cap_bound: int | None
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None
    tool_call_totals: Mapping[str, int]
    safety_cap_hits: int
    stop_reason_counts: Mapping[str, int]
    gap: EvidenceGap  # grader-aware gap from a representative failing run (or last run)
    edits: EditPaths  # edit signals from a representative run
    administrative: bool
    # attempts that were not valid (env-masked); spec §6 invalid case
    invalid_trials: int
    # (category, subcategory) per failing valid run
    classifications: tuple[tuple[str, str], ...]


@dataclass(frozen=True, kw_only=True)
class TaskQuickRef:
    task_id: str
    target_paths: tuple[str, ...]
    grader_id: str
    # EvidenceGap.oracle_total of a representative run (F only)
    oracle_total: int | None


@dataclass(frozen=True, kw_only=True)
class TaskDetail:
    task_id: str
    cells: tuple[TaskConditionCell, ...]  # one per condition, sorted by condition_id
    # intersection of failing_units across failing conds
    shared_failing_units: tuple[str, ...]
    divergent: bool  # True iff the intersection is empty but >1 failing cond


@dataclass(frozen=True, kw_only=True)
class M1Detail:
    domain: str
    conditions_present: tuple[str, ...]
    k: int
    spec_hash: str
    task_quick_refs: tuple[TaskQuickRef, ...]
    tasks: tuple[TaskDetail, ...]
    defect_candidates: tuple[TaskDefectCandidate, ...]
    # one per condition (domain-scoped, sorted)
    efficiency: tuple[CondDomainEfficiency, ...]
    efficiency_condition_ids: tuple[str, ...]  # parallel to efficiency, sorted


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _is_administrative(run: RunResult) -> bool:
    """True iff this run was marked as an administrative (not-executed) trial."""
    return bool(run.grade.evidence.get("marked_failed_not_executed", False))


def _dominant_stop_reason(runs: Sequence[RunResult]) -> str:
    counts = _counts([r.trajectory.stop_reason for r in runs])
    if not counts:
        return "—"
    # max count, ties broken lexicographically SMALLEST (consistent with spec)
    max_count = max(counts.values())
    candidates = [sr for sr, c in counts.items() if c == max_count]
    return min(candidates)


def _representative(runs: Sequence[RunResult]) -> RunResult:
    """First failing valid run, else the first valid run (deterministic)."""
    return next((r for r in runs if not r.grade.passed), runs[0])


def _target_paths_of(run: RunResult) -> tuple[str, ...]:
    fs = run.trajectory.final_state
    if fs is None:
        return ()
    return tuple(fs.get("target_paths", ()))


def _cell(
    condition_id: str,
    runs: Sequence[RunResult],
    k: int,
    invalid: int,
    pricing: PricingSnapshot,
) -> TaskConditionCell:
    if not runs:
        return TaskConditionCell(
            condition_id=condition_id,
            present=False,
            valid_trials=0,
            passed_trials=0,
            incomplete=True,
            per_trial=(),
            dominant_stop_reason="—",
            rounds_median=0.0,
            rounds_min=0,
            rounds_max=0,
            censored_count=0,
            cap_bound=None,
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            cost_usd=None,
            tool_call_totals={},
            safety_cap_hits=0,
            stop_reason_counts={},
            gap=EvidenceGap(
                grader_id="—",
                oracle_total=None,
                oracle_passed=None,
                failing_units=(),
                displaced_paths=(),
                administrative=False,
                status="incomplete",
            ),
            edits=EditPaths(edited=(), out_of_scope=()),
            administrative=False,
            invalid_trials=invalid,
            classifications=(),
        )
    eff = cond_domain_efficiency(runs=runs, condition_id=condition_id, pricing=pricing)
    rep = _representative(runs)
    gap = evidence_gap(rep.grade)
    edits = edit_paths(rep.trajectory, target_paths=_target_paths_of(rep))
    classifications = tuple(
        (c.category, c.subcategory or "—")
        for c in (classify_run(r) for r in runs if not r.grade.passed)
    )
    return TaskConditionCell(
        condition_id=condition_id,
        present=True,
        valid_trials=len(runs),
        passed_trials=sum(1 for r in runs if r.grade.passed),
        incomplete=len(runs) < k,
        per_trial=tuple(r.grade.passed for r in runs),
        dominant_stop_reason=_dominant_stop_reason(runs),
        rounds_median=eff.rounds_median,
        rounds_min=eff.rounds_min,
        rounds_max=eff.rounds_max,
        censored_count=eff.censored_count,
        cap_bound=eff.cap_bound,
        prompt_tokens=eff.prompt_tokens,
        completion_tokens=eff.completion_tokens,
        total_tokens=eff.total_tokens,
        cost_usd=eff.cost_usd,
        tool_call_totals=eff.tool_call_totals,
        safety_cap_hits=eff.safety_cap_hits,
        stop_reason_counts=eff.stop_reason_counts,
        gap=gap,
        edits=edits,
        administrative=gap.administrative,
        invalid_trials=invalid,
        classifications=classifications,
    )


def build_m1_detail(
    *,
    domain: str,
    outcomes_by_condition: Mapping[str, Sequence[ReplacementOutcome]],
    pricing: PricingSnapshot,
    spec: ExperimentSpec,
) -> M1Detail:
    conditions_present = tuple(sorted(outcomes_by_condition))
    # Accumulate runs and invalid counts separately to avoid mutating tuple-held lists
    # (CLAUDE.md: never mutate — use separate dicts, defer any tuple wrapping to read).
    # runs_by_task_cond: (task_id, cond) -> list of valid RunResult (appended immutably)
    runs_by_task_cond: dict[str, dict[str, list[RunResult]]] = {}
    # invalid_by_task_cond: (task_id, cond) -> cumulative invalid attempt count
    invalid_by_task_cond: dict[str, dict[str, int]] = {}
    # valid_by_cond: ALL valid runs (filtered later for defect + efficiency)
    valid_by_cond: dict[str, list[RunResult]] = {c: [] for c in conditions_present}
    for cond in conditions_present:
        for outcome in outcomes_by_condition[cond]:
            invalid = sum(1 for a in outcome.attempts if not a.valid)
            for run in outcome.valid_runs:
                runs_by_task_cond.setdefault(run.task_id, {}).setdefault(
                    cond, []
                ).append(run)
                valid_by_cond[cond].append(run)
            # attribute invalid attempts to the outcome's task (first valid run's
            # task_id, or skip if a fully-void outcome has no valid runs).
            # SUM invalid counts across multiple outcomes for the same (task, cond).
            if outcome.valid_runs:
                tid = outcome.valid_runs[0].task_id
                task_inv = invalid_by_task_cond.setdefault(tid, {})
                task_inv[cond] = task_inv.get(cond, 0) + invalid

    tasks: list[TaskDetail] = []
    quick: list[TaskQuickRef] = []
    for task_id in sorted(runs_by_task_cond):
        task_runs = runs_by_task_cond[task_id]
        task_inv = invalid_by_task_cond.get(task_id, {})
        cells = tuple(
            _cell(
                cond,
                task_runs.get(cond, []),
                spec.k,
                task_inv.get(cond, 0),
                pricing,
            )
            for cond in conditions_present
        )
        # Exclude administrative cells from failing_cells (spec §6 / Finding 1)
        failing_cells = [
            c
            for c in cells
            if c.present
            and c.passed_trials == 0
            and c.valid_trials
            and not c.administrative
        ]
        failing_unit_sets = [set(c.gap.failing_units) for c in failing_cells]
        if failing_unit_sets:
            shared = set.intersection(*failing_unit_sets)
        else:
            shared = set()
        divergent = len(failing_cells) > 1 and not shared
        tasks.append(
            TaskDetail(
                task_id=task_id,
                cells=cells,
                shared_failing_units=tuple(sorted(shared)),
                divergent=divergent,
            )
        )
        rep_cell = next((c for c in cells if c.present), cells[0])
        target_paths: tuple[str, ...] = ()
        rep_runs = task_runs.get(rep_cell.condition_id, [])
        if rep_runs:
            target_paths = _target_paths_of(_representative(rep_runs))
        quick.append(
            TaskQuickRef(
                task_id=task_id,
                target_paths=tuple(target_paths),
                grader_id=rep_cell.gap.grader_id,
                oracle_total=rep_cell.gap.oracle_total,
            )
        )

    # Exclude administrative runs from defect candidates and efficiency (Finding 1)
    real_by_cond: dict[str, list[RunResult]] = {
        cond: [r for r in valid_by_cond[cond] if not _is_administrative(r)]
        for cond in conditions_present
    }
    defect_candidates = task_defect_candidates(
        tuple(
            DefectInputGroup(label=cond, runs=tuple(real_by_cond[cond]), blocked=False)
            for cond in conditions_present
        )
    )
    efficiency = tuple(
        cond_domain_efficiency(
            runs=tuple(real_by_cond[cond]), condition_id=cond, pricing=pricing
        )
        for cond in conditions_present
    )
    return M1Detail(
        domain=domain,
        conditions_present=conditions_present,
        k=spec.k,
        spec_hash=spec.spec_hash,
        task_quick_refs=tuple(quick),
        tasks=tuple(tasks),
        defect_candidates=defect_candidates,
        efficiency=efficiency,
        efficiency_condition_ids=conditions_present,
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------


def _per_trial_str(per_trial: tuple[bool, ...]) -> str:
    return "".join("✅" if p else "❌" for p in per_trial) or "—"


def _rounds_cell(
    median_val: float, lo: int, hi: int, censored: int, cap: int | None
) -> str:
    base = f"{median_val:g} [{lo}–{hi}]"
    if censored > 0:
        bound = "cap" if cap is None else f"cap {cap}"
        base += f" ({censored} right-censored at {bound})"
    return base


def _gap_phrase(gap: EvidenceGap) -> str:
    if gap.administrative:
        return "administrative — not executed (owner decision)"
    if gap.status == "no_answer":
        return "no answer (no assistant message)"
    if gap.oracle_total is not None:
        failing = ", ".join(f"`{u}`" for u in gap.failing_units) or "none"
        return (
            f"passed {gap.oracle_passed}/{gap.oracle_total} oracle tests; "
            f"failing: {failing}"
        )
    if gap.failing_units:
        facts = ", ".join(f"`{u}`" for u in gap.failing_units)
        return "missed/forbidden facts: " + facts
    return gap.status


def _header_lines(detail: M1Detail) -> list[str]:
    conds = ", ".join(detail.conditions_present) or "(none)"
    return [
        f"# M1 subreport — {detail.domain}",
        "",
        f"- conditions: {conds}",
        f"- k={detail.k} · tasks={len(detail.tasks)} · spec_hash=`{detail.spec_hash}`",
        "",
    ]


def _quickref_lines(detail: M1Detail) -> list[str]:
    lines = [
        "## Task quick-reference",
        "",
        "| task | target_paths | grader | oracle tests |",
        "| --- | --- | --- | --- |",
    ]
    for ref in detail.task_quick_refs:
        paths = ", ".join(f"`{p}`" for p in ref.target_paths) or "—"
        oracle = str(ref.oracle_total) if ref.oracle_total is not None else "—"
        lines.append(f"| {ref.task_id} | {paths} | {ref.grader_id} | {oracle} |")
    return lines + [""]


def _summary_lines(detail: M1Detail) -> list[str]:
    lines = [
        "## Cross-model summary",
        "",
        "| task | " + " | ".join(detail.conditions_present) + " | dominant stop |",
        "| --- | " + " | ".join("---" for _ in detail.conditions_present) + " | --- |",
    ]
    for task in detail.tasks:
        cells_by_cond = {c.condition_id: c for c in task.cells}
        row_parts = []
        for cond in detail.conditions_present:
            c = cells_by_cond.get(cond)
            if c is None or not c.present:
                row_parts.append("—")
            elif c.administrative:
                # Administrative: owner decided not to execute — never a real failure
                row_parts.append("— admin (not executed)")
            else:
                row_parts.append(
                    f"{c.passed_trials}/{c.valid_trials} {_per_trial_str(c.per_trial)}"
                )
        dominant = cells_by_cond.get(detail.conditions_present[0])
        dom_stop = (
            dominant.dominant_stop_reason if dominant and dominant.present else "—"
        )
        lines.append(
            f"| {task.task_id} | " + " | ".join(row_parts) + f" | {dom_stop} |"
        )
    return lines + [""]


def _per_task_cell_lines(cell: TaskConditionCell, k: int) -> list[str]:
    lines = [f"#### Condition: `{cell.condition_id}`", ""]
    if not cell.present:
        lines += ["— (condition has no records for this task)", ""]
        return lines
    if cell.administrative:
        lines += [
            f"administrative 0/{k} — not executed (owner decision)",
            "",
        ]
        return lines
    status_note = ""
    if cell.incomplete:
        status_note = (
            f" — **status = incomplete (excluded from pass^k)**"
            f" ({cell.valid_trials}/{k} valid trials)"
        )
    trial_str = _per_trial_str(cell.per_trial)
    rounds = _rounds_cell(
        cell.rounds_median,
        cell.rounds_min,
        cell.rounds_max,
        cell.censored_count,
        cell.cap_bound,
    )
    cost = "—" if cell.cost_usd is None else f"{cell.cost_usd:.6f}"
    total_tools = sum(cell.tool_call_totals.values())
    lines += [
        f"- pass: {cell.passed_trials}/{cell.valid_trials}{status_note} — {trial_str}",
        f"- rounds: {rounds}",
        (
            f"- tokens: prompt={cell.prompt_tokens}"
            f" / completion={cell.completion_tokens}"
            f" / total={cell.total_tokens}"
        ),
        f"- cost_usd: {cost}",
        f"- tool calls (total): {total_tools}",
        f"- safety-cap hits: {cell.safety_cap_hits}",
        f"- dominant stop: {cell.dominant_stop_reason}",
        f"- grader gap: {_gap_phrase(cell.gap)}",
    ]
    if cell.gap.displaced_paths:
        lines.append(
            "- displaced (oracle overlay): "
            + ", ".join(f"`{p}`" for p in cell.gap.displaced_paths)
        )
    edited = ", ".join(f"`{p}`" for p in cell.edits.edited) or "—"
    oos = ", ".join(f"`{p}`" for p in cell.edits.out_of_scope) or "—"
    lines += [
        f"- edited: {edited}",
        f"- out-of-scope edits: {oos}",
    ]
    if cell.invalid_trials > 0:
        lines.append(
            f"- invalid (env-masked) trials: {cell.invalid_trials}"
            " — excluded, not a model gap"
        )
    lines.append("")
    return lines


def _per_task_lines(detail: M1Detail) -> list[str]:
    lines = ["## Per-task detail", ""]
    for task in detail.tasks:
        lines += [f"### Task: `{task.task_id}`", ""]
        for cell in task.cells:
            lines += _per_task_cell_lines(cell, detail.k)
    return lines


def _defect_lines(detail: M1Detail) -> list[str]:
    lines = [
        "## Task-defect candidates",
        "",
        "Tasks that every non-blocked condition with records unanimously fails. "
        "Flagged for human review, never auto-classified (ADR-0013).",
        "",
    ]
    if not detail.defect_candidates:
        lines += ["(none)", ""]
        return lines
    # build a lookup from task_id to TaskDetail for shared units
    task_map = {t.task_id: t for t in detail.tasks}
    for cand in detail.defect_candidates:
        t = task_map.get(cand.task_id)
        if t and t.shared_failing_units:
            shared_txt = "shared failing oracle unit(s): " + ", ".join(
                f"`{u}`" for u in t.shared_failing_units
            )
        elif t and t.divergent:
            shared_txt = "divergent failures (no shared unit)"
        else:
            shared_txt = "(no shared unit data)"
        lines += [
            f"- `{cand.task_id}` ({cand.n_conditions} conditions, {cand.n_runs} runs)",
            f"  - {shared_txt}",
        ]
    lines.append("")
    return lines


def _efficiency_lines(detail: M1Detail) -> list[str]:
    lines = [
        "## Per-condition efficiency",
        "",
        "| condition | rounds median [min–max] | prompt tok | completion tok "
        "| total tok | cost (USD) | tool calls | safety-cap hits | max-rounds hits "
        "| dominant stop |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for cond, eff in zip(detail.efficiency_condition_ids, detail.efficiency):
        rounds = _rounds_cell(
            eff.rounds_median,
            eff.rounds_min,
            eff.rounds_max,
            eff.censored_count,
            eff.cap_bound,
        )
        cost = "—" if eff.cost_usd is None else f"{eff.cost_usd:.4f}"
        total_tools = sum(eff.tool_call_totals.values())
        if eff.stop_reason_counts:
            _max_cnt = max(eff.stop_reason_counts.values())
            dominant = min(
                sr for sr, c in eff.stop_reason_counts.items() if c == _max_cnt
            )
        else:
            dominant = "—"
        lines.append(
            f"| {cond} | {rounds} | {eff.prompt_tokens} | {eff.completion_tokens} "
            f"| {eff.total_tokens} | {cost} | {total_tools} | {eff.safety_cap_hits} "
            f"| {eff.max_rounds_hits} | {dominant} |"
        )
    return lines + [""]


def _classification_lines(detail: M1Detail) -> list[str]:
    lines = ["## Failure classification (fc-v4) per task × condition", ""]
    for task in detail.tasks:
        for cell in task.cells:
            if not cell.present or not cell.classifications or cell.administrative:
                continue
            lines.append(f"### `{task.task_id}` × `{cell.condition_id}`")
            lines += [
                "",
                "| category | subcategory |",
                "| --- | --- |",
            ]
            for cat, sub in cell.classifications:
                lines.append(f"| {cat} | {sub} |")
            lines.append("")
    if len(lines) == 2:  # only the header
        lines += ["(no failures classified)", ""]
    return lines


def render_detail(detail: M1Detail) -> str:
    body: list[str]
    if not detail.tasks:
        # Void domain: all runs were voided or absent; emit an explicit note (spec §6)
        body = [
            "_(no executed tasks — all runs voided or absent)_",
            "",
        ]
    else:
        body = (
            _quickref_lines(detail)
            + _summary_lines(detail)
            + _per_task_lines(detail)
            + _defect_lines(detail)
            + _efficiency_lines(detail)
            + _classification_lines(detail)
        )
    lines = _header_lines(detail) + body
    return "\n".join(lines) + "\n"
