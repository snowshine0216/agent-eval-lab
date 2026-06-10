"""EDGE: the provisional two-LLM-annotator run (AC 9, D12).

Routes each fixture's trajectory through the SAME build_judge_prompt -> run_judge
-> packet pipeline a human annotator's packet uses. A JudgeError on a fixture
records score=None for that item (an annotator-failure marker), never a crash and
never a coerced score. LLM-LLM agreement is NOT the human-human reliability the
protocol requires — every artifact built from this is labeled PROVISIONAL.
"""

import dataclasses
from collections.abc import Mapping, Sequence

import httpx

from agent_eval_lab.calibrate.packet import Packet, build_packet
from agent_eval_lab.graders.judge import JudgeVerdict
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.judge_edge import run_judge
from agent_eval_lab.tasks.schema import LlmJudgeSpec


def run_provisional_labeling(
    *,
    fixtures: Sequence[tuple[str, Trajectory]],
    rubric: str,
    config: ProviderConfig,
    annotator_id: str,
    http_client: httpx.Client,
) -> Packet:
    spec = LlmJudgeSpec(rubric=rubric, judge_model=annotator_id, scale=(1, 5))
    blank = build_packet(fixtures=fixtures, spec=spec, rubric=rubric)
    scored = []
    for item, (_, traj) in zip(blank.items, fixtures):
        verdict = run_judge(
            spec=spec, trajectory=traj, config=config, http_client=http_client
        )
        score = verdict.score if isinstance(verdict, JudgeVerdict) else None
        scored.append(dataclasses.replace(item, score=score))
    return dataclasses.replace(blank, items=tuple(scored), annotator_id=annotator_id)


def render_provisional_summary(
    report: Mapping[str, object], *, models: Sequence[str], skipped: Sequence[str]
) -> str:
    bk = report["binary_kappa"]
    ci = bk["ci"]
    banner = (
        "> **PROVISIONAL — LLM-LLM agreement, NOT the human-human reliability that\n"
        "> calibration protocol step 2 requires.**"
        " Steps 2 (>=2 human annotators) and 3\n"
        "> (judge-human kappa) remain OPEN. See SKIPPED.md and the calibration\n"
        "> runbook for the unblock path: the user fills the packet, recruits\n"
        "> annotator #2, and re-runs `calibrate compute` to replace these numbers.\n"
    )
    ci_line = (
        f"- {int((1 - ci['alpha']) * 100)}% percentile bootstrap CI = "
        f"[{ci['lo']:.4f}, {ci['hi']:.4f}]"
        f" (n_resamples={ci['n_resamples']}, seed={ci['seed']},"
        f" degenerate_resamples={ci['n_degenerate']})"
    )
    obs_line = (
        f"- observed agreement = {bk['observed_agreement']:.4f};"
        f" degenerate={bk['degenerate']}"
    )
    return "\n".join([
        "# Calibration — PROVISIONAL summary",
        "",
        banner,
        f"- Annotator models that ran: {list(models)}",
        f"- Models skipped (missing key): {list(skipped)}",
        f"- Binary Cohen's kappa (LLM-LLM) = {bk['point']:.4f}",
        ci_line,
        f"- Weighted (quadratic) kappa = {report['weighted_kappa']:.4f}",
        obs_line,
        "",
        "At n in [12,20] the bootstrap CI is wide and n-dominated:",
        "a plumbing/feasibility number, not a reliability verdict (see runbook).",
        "",
    ]) + "\n"
