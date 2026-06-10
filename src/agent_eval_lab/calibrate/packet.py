"""Pure annotation-packet build/parse/validate + agreement computation (spec §6.5).

The packet a human (or LLM annotator) sees is BLIND: trajectory digest only, an
empty score field, NO judge score and NO fixture intended label (the intended
label lives in examples/calibration/intended_labels.jsonl, never here — D9).
JSONL is the source of truth; a sibling markdown is a human-readable view.
"""

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from agent_eval_lab.graders.judge import render_trajectory_digest
from agent_eval_lab.metrics.agreement import (
    cohens_kappa,
    confusion_matrix,
    kappa_bootstrap_ci,
    weighted_kappa,
)
from agent_eval_lab.records.trajectory import Trajectory
from agent_eval_lab.tasks.schema import LlmJudgeSpec

PACKET_FORMAT = "calib-packet-v1"
RUBRIC_VERSION = "summary-fidelity-v1"


@dataclass(frozen=True, kw_only=True)
class PacketItem:
    fixture_id: str
    trajectory_digest: str
    score: int | None = None


@dataclass(frozen=True, kw_only=True)
class Packet:
    packet_format: str
    rubric_version: str
    rubric: str
    annotator_id: str | None
    items: tuple[PacketItem, ...]


def build_packet(
    *,
    fixtures: Sequence[tuple[str, Trajectory]],
    spec: LlmJudgeSpec,
    rubric: str,
) -> Packet:
    # `spec` is validated and kept in the signature so the packet's scale is an
    # explicit input (matches the test call sites and documents the judged scale);
    # the stored rubric is the verbatim anchors, unmodified.
    lo, hi = spec.scale
    if lo >= hi:
        raise ValueError(f"spec.scale must have lo < hi, got {spec.scale!r}")
    items = tuple(
        PacketItem(
            fixture_id=fid,
            trajectory_digest=render_trajectory_digest(traj),
            score=None,
        )
        for fid, traj in fixtures
    )
    return Packet(
        packet_format=PACKET_FORMAT,
        rubric_version=RUBRIC_VERSION,
        rubric=rubric,
        annotator_id=None,
        items=items,
    )


def packet_to_jsonl(packet: Packet) -> str:
    header = {
        "packet_format": packet.packet_format,
        "rubric_version": packet.rubric_version,
        "rubric": packet.rubric,
        "annotator_id": packet.annotator_id,
    }
    lines = [json.dumps(header, sort_keys=True)]
    lines.extend(
        json.dumps(
            {
                "fixture_id": i.fixture_id,
                "trajectory_digest": i.trajectory_digest,
                "score": i.score,
            },
            sort_keys=True,
        )
        for i in packet.items
    )
    return "\n".join(lines) + "\n"


def packet_from_jsonl(text: str) -> Packet:
    raw = [json.loads(line) for line in text.splitlines() if line.strip()]
    header, body = raw[0], raw[1:]
    return Packet(
        packet_format=header["packet_format"],
        rubric_version=header["rubric_version"],
        rubric=header["rubric"],
        annotator_id=header.get("annotator_id"),
        items=tuple(
            PacketItem(
                fixture_id=r["fixture_id"],
                trajectory_digest=r["trajectory_digest"],
                score=r["score"],
            )
            for r in body
        ),
    )


def import_packet(
    text: str, *, expected: Packet, scale: tuple[int, int] = (1, 5)
) -> Packet:
    """Parse a filled packet and validate completeness against the exported one.

    Rejects (structured ValueError): packet_format mismatch, item-set/order
    mismatch, any unscored item, any score out of `scale`.
    """
    packet = packet_from_jsonl(text)
    if packet.packet_format != expected.packet_format:
        raise ValueError(
            f"packet_format mismatch: {packet.packet_format!r} != "
            f"{expected.packet_format!r}"
        )
    got_ids = [i.fixture_id for i in packet.items]
    want_ids = [i.fixture_id for i in expected.items]
    if got_ids != want_ids:
        raise ValueError(f"item order/set mismatch: {got_ids} != {want_ids}")
    lo, hi = scale
    for item in packet.items:
        if item.score is None:
            raise ValueError(f"unscored item: {item.fixture_id!r}")
        if not (lo <= item.score <= hi):
            raise ValueError(
                f"score out of range for {item.fixture_id!r}: {item.score}"
            )
    return packet


def _binarize(score: int, threshold: int) -> str:
    return "faithful" if score >= threshold else "unfaithful"


def compute_agreement(
    packets: Sequence[Packet],
    *,
    threshold: int,
    scale: tuple[int, int],
    seed: int,
    n_resamples: int,
    alpha: float,
) -> Mapping[str, object]:
    """Two-rater agreement over the FIRST TWO filled packets (Cohen's kappa, §6.5).

    Headline = binary kappa at `threshold` + percentile bootstrap CI; weighted
    kappa (quadratic, over the raw scale) is a secondary descriptive number.
    """
    if len(packets) < 2:
        raise ValueError("agreement requires at least two annotators")
    a_pkt, b_pkt = packets[0], packets[1]
    a_scores = [i.score for i in a_pkt.items]
    b_scores = [i.score for i in b_pkt.items]
    a_bin = [_binarize(s, threshold) for s in a_scores]
    b_bin = [_binarize(s, threshold) for s in b_scores]
    binary = cohens_kappa(a_bin, b_bin)
    ci = kappa_bootstrap_ci(
        a_bin, b_bin, n_resamples=n_resamples, seed=seed, alpha=alpha
    )
    categories = tuple(range(scale[0], scale[1] + 1))
    return {
        "n_items": len(a_scores),
        "annotators": (a_pkt.annotator_id, b_pkt.annotator_id),
        "threshold": threshold,
        "binary_kappa": {
            "point": binary.kappa,
            "observed_agreement": binary.observed_agreement,
            "expected_agreement": binary.expected_agreement,
            "degenerate": binary.degenerate,
            "ci": {
                "lo": ci.lo, "hi": ci.hi, "alpha": ci.alpha,
                "n_resamples": ci.n_resamples,
                "n_degenerate": ci.n_degenerate,
                "seed": ci.seed,
            },
        },
        "weighted_kappa": weighted_kappa(a_scores, b_scores, categories=categories),
        "confusion_matrix": confusion_matrix(a_bin, b_bin),
    }


def render_agreement_report(report: Mapping[str, object]) -> str:
    bk = report["binary_kappa"]
    ci = bk["ci"]
    cm = report["confusion_matrix"]
    lines = [
        "# Calibration agreement report",
        "",
        f"- Annotators: {report['annotators']}",
        f"- Items: {report['n_items']}",
        f"- Binarization threshold: score >= {report['threshold']} => faithful",
        "",
        "## Headline: binary Cohen's kappa (ADR 0006)",
        f"- kappa = {bk['point']:.4f}",
        (
            f"- {int((1 - ci['alpha']) * 100)}% percentile bootstrap CI = "
            f"[{ci['lo']:.4f}, {ci['hi']:.4f}] "
            f"(n_resamples={ci['n_resamples']}, seed={ci['seed']}, "
            f"degenerate_resamples={ci['n_degenerate']})"
        ),
        (
            f"- observed agreement = {bk['observed_agreement']:.4f}; "
            f"expected = {bk['expected_agreement']:.4f}; degenerate={bk['degenerate']}"
        ),
        "",
        "## Secondary: quadratic-weighted kappa (descriptive)",
        f"- weighted kappa = {report['weighted_kappa']:.4f}",
        "",
        "## Confusion matrix (binary)",
        "| A \\\\ B | faithful | unfaithful |",
        "|---|---|---|",
        (
            f"| faithful | {cm.get(('faithful', 'faithful'), 0)} | "
            f"{cm.get(('faithful', 'unfaithful'), 0)} |"
        ),
        (
            f"| unfaithful | {cm.get(('unfaithful', 'faithful'), 0)} | "
            f"{cm.get(('unfaithful', 'unfaithful'), 0)} |"
        ),
    ]
    return "\n".join(lines) + "\n"
