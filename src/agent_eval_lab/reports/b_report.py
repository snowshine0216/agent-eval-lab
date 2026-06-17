"""PURE: join owner verdicts with grade-less BTrials -> per-(model, arm) B-1
metrics (spec §5 / §6 / ADR-0021).

report_b(trials, verdicts, pricing) constructs the grade from the owner verdict at
report time — never a fabricated run-time GradeResult. Per (condition, arm):
headline pass_at_1 (per-trial pass rate over VALID verdicts), secondary pass_pow_3
(all-k pass), valid/invalid counts, mean/median rounds/tokens/cost/wall-time; plus
the descriptive skill delta on pass_at_1 (skill - noskill) per model. A condition
whose id is a subprocess (claude-cli:*) driver is FLAGGED (is_subprocess_driver) so
the renderer keeps its turns/USD on a separate efficiency axis (decision 5) and its
cost comes from total_cost_usd, not tokens x pricing.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from statistics import mean, median

from agent_eval_lab.metrics.cost import TokenPrice
from agent_eval_lab.records.b_trial import BTrial

OwnerVerdict = str  # "PASS" | "FAIL" | "INVALID"

_NOSKILL = "b-b1-noskill"
_SKILL = "b-b1-skill"


def _is_subprocess_driver(condition_id: str) -> bool:
    """claude -p is a subprocess driver — its efficiency (turns / subscription-USD)
    rides a SEPARATE axis, never pooled with chat-model rounds/cost (decision 5)."""
    return condition_id.startswith("claude-cli:")


@dataclass(frozen=True, kw_only=True)
class BReportRow:
    condition_id: str
    arm: str
    valid: int  # trials with a PASS/FAIL verdict (INVALID excluded)
    invalid: int  # trials whose verdict is INVALID (or missing)
    pass_at_1: float  # headline: passes / valid
    pass_pow_3: bool  # secondary: valid >= 3 AND all valid passed
    mean_rounds: float
    median_rounds: float
    mean_tokens: float
    cost_usd: float  # chat: tokens x pricing; claude: sum total_cost_usd
    mean_wall_time_s: float
    is_subprocess_driver: bool


@dataclass(frozen=True, kw_only=True)
class BReport:
    rows: tuple[BReportRow, ...]
    skill_delta: Mapping[
        str, float
    ]  # condition_id -> pass_at_1(skill) - pass_at_1(noskill)


def _verdict_for(trial: BTrial, verdicts: Mapping[str, OwnerVerdict]) -> str:
    """The owner verdict for a trial, defaulting a missing one to INVALID (the
    runner auto-tagged trial is invalid; a missing owner verdict is treated as
    INVALID, never a silent FAIL — anti-silent discipline)."""
    if trial.invalid:
        return "INVALID"
    return verdicts.get(trial.run_uid, "INVALID")


def _cost(
    trials: Sequence[BTrial], *, condition_id: str, pricing: Mapping[str, TokenPrice]
) -> float:
    if _is_subprocess_driver(condition_id):
        return sum((t.trajectory.total_cost_usd or 0.0) for t in trials)
    price = pricing.get(condition_id)
    if price is None:
        return 0.0
    pt = sum(t.trajectory.usage.prompt_tokens for t in trials)
    ct = sum(t.trajectory.usage.completion_tokens for t in trials)
    return (pt * price.input_per_mtok + ct * price.output_per_mtok) / 1_000_000


def _row(
    condition_id: str,
    arm: str,
    trials: Sequence[BTrial],
    verdicts: Mapping[str, OwnerVerdict],
    pricing: Mapping[str, TokenPrice],
) -> BReportRow:
    scored = [(t, _verdict_for(t, verdicts)) for t in trials]
    valid = [(t, v) for t, v in scored if v in ("PASS", "FAIL")]
    passes = sum(1 for _, v in valid if v == "PASS")
    n_valid = len(valid)
    valid_trials = [t for t, _ in valid]
    rounds = [t.trajectory.rounds for t in valid_trials] or [0]
    tokens = [
        t.trajectory.usage.prompt_tokens + t.trajectory.usage.completion_tokens
        for t in valid_trials
    ] or [0]
    walls = [t.trajectory.wall_time_s for t in valid_trials] or [0.0]
    return BReportRow(
        condition_id=condition_id,
        arm=arm,
        valid=n_valid,
        invalid=len(trials) - n_valid,
        pass_at_1=(passes / n_valid) if n_valid else 0.0,
        pass_pow_3=(n_valid >= 3 and passes == n_valid),
        mean_rounds=mean(rounds),
        median_rounds=median(rounds),
        mean_tokens=mean(tokens),
        cost_usd=_cost(valid_trials, condition_id=condition_id, pricing=pricing),
        mean_wall_time_s=mean(walls),
        is_subprocess_driver=_is_subprocess_driver(condition_id),
    )


def report_b(
    trials: Sequence[BTrial],
    verdicts: Mapping[str, OwnerVerdict],
    *,
    pricing: Mapping[str, TokenPrice],
) -> BReport:
    """Build the B-1 report. PURE — no I/O. `verdicts` maps run_uid -> owner verdict."""
    by_key: dict[tuple[str, str], list[BTrial]] = {}
    for t in trials:
        by_key.setdefault((t.condition_id, t.task_id), []).append(t)
    rows = tuple(
        _row(cond, arm, group, verdicts, pricing)
        for (cond, arm), group in sorted(by_key.items())
    )
    # Skill delta on pass_at_1 (skill - noskill) per model, where both arms exist.
    pa1: dict[tuple[str, str], float] = {
        (r.condition_id, r.arm): r.pass_at_1 for r in rows
    }
    conditions = sorted({r.condition_id for r in rows})
    skill_delta = {
        c: pa1[(c, _SKILL)] - pa1[(c, _NOSKILL)]
        for c in conditions
        if (c, _SKILL) in pa1 and (c, _NOSKILL) in pa1
    }
    return BReport(rows=rows, skill_delta=skill_delta)


def render_b_report(report: BReport) -> str:
    """Render the B-1 report markdown. PURE. claude -p efficiency is on its own
    axis (turns (Claude Code) / USD (subscription-equiv)); B-1 is a ONE-TASK
    contingency (never a CI labelled as bootstrap)."""
    lines = [
        "# B-1 Live Spike report (human-scored — owner verdict)",
        "",
        "> B-1 is a ONE-TASK contingency (point summary, not a cluster bootstrap CI).",
        "",
        "| model | arm | valid | invalid | pass_at_1 | pass_pow_3 | mean_rounds | "
        "cost_usd | efficiency_axis |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in report.rows:
        axis = (
            "turns (Claude Code) / USD (subscription-equiv)"
            if r.is_subprocess_driver
            else "rounds / token-USD"
        )
        lines.append(
            f"| {r.condition_id} | {r.arm} | {r.valid} | {r.invalid} | "
            f"{r.pass_at_1:.3f} | {r.pass_pow_3} | {r.mean_rounds:.1f} | "
            f"{r.cost_usd:.4f} | {axis} |"
        )
    lines += ["", "## Skill delta on pass_at_1 (skill − noskill)", ""]
    for cond, delta in sorted(report.skill_delta.items()):
        lines.append(f"- {cond}: {delta:+.3f}")
    return "\n".join(lines) + "\n"
