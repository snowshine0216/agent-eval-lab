"""Pure two-configuration comparison report (item 004). Build + render, no I/O.

A = `default` (per-task author prompt, no override); B = `planning` (the
committed planning-v1 fixture). Both share condition_id deepseek:deepseek-v4-pro;
they are identified by SOURCE PATH (ADR-0007), passed explicitly. The primary
metric is the T3+T4 paired Δ pass^3 CI (Resolved Q3); the overall-50 Δ is
secondary/descriptive. The verdict is read MECHANICALLY off the T3+T4 CI per the
frozen decision rule. The planning prompt is hash-pinned (sha256-over-canonical
bytes, Resolved Q5) reusing the graders/canonical + hashlib precedent.
"""

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.graders.canonical import canonicalize
from agent_eval_lab.metrics.agreement import BootstrapCI
from agent_eval_lab.metrics.reliability import (
    paired_pass_pow_k_diff_ci,
    pass_at_1,
    pass_pow_k,
    pass_pow_k_by_tier,
    tier_of,
)
from agent_eval_lab.records.grade import RunResult

HYPOTHESIS = (
    "Configuration B (planning) achieves a higher pass^3 on the hard tiers "
    "(T3+T4) than Configuration A, because the v1/v2 failure signal is "
    "over-calling and mis-tracking derived/minted ids on multi-step chains; an "
    "explicit 'identify before you modify' step should suppress extra_call and "
    "wrong_args on multi_step_state / derived_reasoning / constraint_compliance "
    "tasks. On T1+T2 the two configs are expected to be statistically "
    "indistinguishable (both near-ceiling)."
)


@dataclass(frozen=True, kw_only=True)
class ComparisonReport:
    config_a_label: str
    config_b_label: str
    config_a_path: str
    config_b_path: str
    planning_prompt_hash: str
    k: int
    seed: int
    n_tasks: int
    pass_pow_k_a: float
    pass_pow_k_b: float
    pass_at_1_a: float
    pass_at_1_b: float
    by_tier_a: Mapping[str, float]
    by_tier_b: Mapping[str, float]
    delta_hard: BootstrapCI  # T3+T4 — PRIMARY
    delta_overall: BootstrapCI  # all paired tasks — SECONDARY
    extra_call_rate_a: float
    extra_call_rate_b: float
    wrong_args_rate_a: float
    wrong_args_rate_b: float
    tokens_a: tuple[int, int]
    tokens_b: tuple[int, int]
    verdict: str


def _prompt_hash(text: str) -> str:
    """sha256 over canonical bytes of the prompt (Resolved Q5). The prompt is a
    plain string; canonicalize is a no-op on scalars, so this is sha256 of the
    UTF-8 bytes — the same machinery item 003 uses for judge prompts."""
    canonical = canonicalize(text)
    return hashlib.sha256(str(canonical).encode("utf-8")).hexdigest()


def _failure_rate(results: Sequence[RunResult], category: str) -> float:
    if not results:
        return 0.0
    hits = sum(1 for r in results if r.grade.failure_reason == category)
    return hits / len(results)


def _hard_subset(
    results: Sequence[RunResult], tiers: Mapping[str, str]
) -> tuple[RunResult, ...]:
    return tuple(r for r in results if tier_of(r.task_id, tiers) in ("T3", "T4"))


def _tokens(results: Sequence[RunResult]) -> tuple[int, int]:
    return (
        sum(r.trajectory.usage.prompt_tokens for r in results),
        sum(r.trajectory.usage.completion_tokens for r in results),
    )


def _verdict(delta_hard: BootstrapCI) -> str:
    if delta_hard.lo > 0:
        return "planning helps on hard tiers (hypothesis supported)"
    if delta_hard.hi < 0:
        return "planning hurts on hard tiers (pre-registered surprise outcome)"
    return (
        "no detectable effect at n=50 — the T3+T4 Δ CI includes 0. With 50 tasks "
        "and near-ceiling rates the interval is wide; absence of a detectable "
        "effect is not evidence of no effect."
    )


def build_comparison_report(
    *,
    results_a: Sequence[RunResult],
    results_b: Sequence[RunResult],
    tiers: Mapping[str, str],
    planning_prompt_text: str,
    config_a_path: str,
    config_b_path: str,
    k: int,
    seed: int,
    n_resamples: int,
    alpha: float,
) -> ComparisonReport:
    hard_a = _hard_subset(results_a, tiers)
    hard_b = _hard_subset(results_b, tiers)
    delta_hard = paired_pass_pow_k_diff_ci(
        hard_a, hard_b, n_resamples=n_resamples, seed=seed, alpha=alpha
    )
    delta_overall = paired_pass_pow_k_diff_ci(
        results_a, results_b, n_resamples=n_resamples, seed=seed, alpha=alpha
    )
    return ComparisonReport(
        config_a_label="default (per-task author prompt, no override)",
        config_b_label="planning (planning-v1 fixture)",
        config_a_path=config_a_path,
        config_b_path=config_b_path,
        planning_prompt_hash=_prompt_hash(planning_prompt_text),
        k=k,
        seed=seed,
        n_tasks=len({r.task_id for r in results_a}),
        pass_pow_k_a=pass_pow_k(results_a),
        pass_pow_k_b=pass_pow_k(results_b),
        pass_at_1_a=pass_at_1(results_a),
        pass_at_1_b=pass_at_1(results_b),
        by_tier_a=pass_pow_k_by_tier(results_a, tiers),
        by_tier_b=pass_pow_k_by_tier(results_b, tiers),
        delta_hard=delta_hard,
        delta_overall=delta_overall,
        extra_call_rate_a=_failure_rate(results_a, "extra_call"),
        extra_call_rate_b=_failure_rate(results_b, "extra_call"),
        wrong_args_rate_a=_failure_rate(results_a, "wrong_args"),
        wrong_args_rate_b=_failure_rate(results_b, "wrong_args"),
        tokens_a=_tokens(results_a),
        tokens_b=_tokens(results_b),
        verdict=_verdict(delta_hard),
    )


def _ci_str(ci: BootstrapCI) -> str:
    return f"{ci.point:+.3f} [{ci.lo:+.3f}, {ci.hi:+.3f}]"


def render_markdown(report: ComparisonReport) -> str:
    tier_order = ("T1", "T2", "T3", "T4")
    lines = [
        "# Configuration comparison — default vs planning",
        "",
        "## Hypothesis (pre-declared, frozen before any run)",
        "",
        HYPOTHESIS,
        "",
        "## Held-fixed factors",
        "",
        "- Model: `deepseek:deepseek-v4-pro` · dataset: `workspace_tool_use_v2` "
        f"(all {report.n_tasks} tasks, paired) · k={report.k}",
        "- Temperature 0.0 *requested* (no seed sent; hosted providers are not "
        "greedy-deterministic at temp 0).",
        "- Registry: WORKSPACE_TOOLS · per-task max_steps honored (ADR-0004).",
        "",
        "## Prompt-config pins (ADR-0007: configs share condition_id; identity is "
        "the source path)",
        "",
        f"- Config A — {report.config_a_label}",
        f"  - artifact: `{report.config_a_path}`",
        f"- Config B — {report.config_b_label}",
        f"  - artifact: `{report.config_b_path}`",
        f"  - planning prompt sha256 (over canonical bytes): "
        f"`{report.planning_prompt_hash}`",
        "",
        "## Per-configuration pass rates",
        "",
        "| metric | A (default) | B (planning) |",
        "| --- | --- | --- |",
        f"| pass^3 (overall, {report.n_tasks} tasks) | {report.pass_pow_k_a:.3f} | "
        f"{report.pass_pow_k_b:.3f} |",
        f"| pass@1 (trial) | {report.pass_at_1_a:.3f} | {report.pass_at_1_b:.3f} |",
        "",
        "### Per-tier pass^3",
        "",
        "| tier | A | B |",
        "| --- | --- | --- |",
    ]
    for t in tier_order:
        av = f"{report.by_tier_a[t]:.3f}" if t in report.by_tier_a else "—"
        bv = f"{report.by_tier_b[t]:.3f}" if t in report.by_tier_b else "—"
        lines.append(f"| {t} | {av} | {bv} |")
    lines += [
        "",
        "## Paired Δ pass^3 (B − A), cluster-bootstrap-by-task 95% CI",
        "",
        f"- **Primary (T3+T4):** Δ = {_ci_str(report.delta_hard)} "
        f"(seed={report.seed}, n_resamples={report.delta_hard.n_resamples})",
        f"- Secondary (overall {report.n_tasks} tasks, descriptive): "
        f"Δ = {_ci_str(report.delta_overall)}",
        "",
        "## Secondary metrics (mechanism + cost; not decisive)",
        "",
        "| metric | A | B |",
        "| --- | --- | --- |",
        f"| extra_call rate | {report.extra_call_rate_a:.3f} | "
        f"{report.extra_call_rate_b:.3f} |",
        f"| wrong_args rate | {report.wrong_args_rate_a:.3f} | "
        f"{report.wrong_args_rate_b:.3f} |",
        f"| prompt tokens | {report.tokens_a[0]} | {report.tokens_b[0]} |",
        f"| completion tokens | {report.tokens_a[1]} | {report.tokens_b[1]} |",
        "",
        "## Decision rule (frozen before running) and verdict",
        "",
        "- If the T3+T4 Δ pass^3 95% CI excludes 0 and lies above 0 → planning "
        "helps on hard tiers.",
        "- If the CI includes 0 → no detectable effect at n=50 (absence of a "
        "detectable effect is not evidence of no effect).",
        "- If the CI excludes 0 and lies below 0 → planning hurts.",
        "",
        f"**Verdict (read mechanically off the T3+T4 Δ CI):** {report.verdict}",
    ]
    return "\n".join(lines) + "\n"
