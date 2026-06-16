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
            tool_totals[tool] = tool_totals.get(tool, 0) + r.trajectory.tool_call_counts[
                tool
            ]
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
    invalid_trials: int  # attempts that were not valid (env-masked); spec §6 invalid case
    classifications: tuple[tuple[str, str], ...]  # (category, subcategory) per failing valid run


@dataclass(frozen=True, kw_only=True)
class TaskQuickRef:
    task_id: str
    target_paths: tuple[str, ...]
    grader_id: str
    oracle_total: int | None  # EvidenceGap.oracle_total of a representative run (F only)


@dataclass(frozen=True, kw_only=True)
class TaskDetail:
    task_id: str
    cells: tuple[TaskConditionCell, ...]  # one per condition, sorted by condition_id
    shared_failing_units: tuple[str, ...]  # intersection of failing_units across failing conds
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
    efficiency: tuple[CondDomainEfficiency, ...]  # one per condition (domain-scoped, sorted)
    efficiency_condition_ids: tuple[str, ...]  # parallel to efficiency, sorted


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _dominant_stop_reason(runs: Sequence[RunResult]) -> str:
    counts = _counts([r.trajectory.stop_reason for r in runs])
    if not counts:
        return "—"
    # max count, ties broken lexicographically smallest
    return max(counts, key=lambda sr: (counts[sr], tuple(-ord(c) for c in sr)))


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
    # (task_id, cond) -> (valid_runs_list, invalid_count)
    by_task_cond: dict[str, dict[str, tuple[list[RunResult], int]]] = {}
    valid_by_cond: dict[str, list[RunResult]] = {c: [] for c in conditions_present}
    for cond in conditions_present:
        for outcome in outcomes_by_condition[cond]:
            invalid = sum(1 for a in outcome.attempts if not a.valid)
            for run in outcome.valid_runs:
                slot = by_task_cond.setdefault(run.task_id, {}).setdefault(
                    cond, ([], 0)
                )
                slot[0].append(run)
                valid_by_cond[cond].append(run)
            # attribute invalid attempts to the outcome's task (first valid run's
            # task_id, or skip if a fully-void outcome has no valid runs).
            if outcome.valid_runs:
                tid = outcome.valid_runs[0].task_id
                runs_list, _ = by_task_cond[tid][cond]
                by_task_cond[tid][cond] = (runs_list, invalid)

    tasks: list[TaskDetail] = []
    quick: list[TaskQuickRef] = []
    for task_id in sorted(by_task_cond):
        cells = tuple(
            _cell(
                cond,
                by_task_cond[task_id].get(cond, ([], 0))[0],
                spec.k,
                by_task_cond[task_id].get(cond, ([], 0))[1],
                pricing,
            )
            for cond in conditions_present
        )
        failing_cells = [
            c for c in cells if c.present and c.passed_trials == 0 and c.valid_trials
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
        rep_runs = by_task_cond[task_id].get(rep_cell.condition_id, ([], 0))[0]
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

    defect_candidates = task_defect_candidates(
        tuple(
            DefectInputGroup(label=cond, runs=tuple(valid_by_cond[cond]), blocked=False)
            for cond in conditions_present
        )
    )
    efficiency = tuple(
        cond_domain_efficiency(
            runs=tuple(valid_by_cond[cond]), condition_id=cond, pricing=pricing
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
