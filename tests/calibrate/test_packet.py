import dataclasses
import json

import pytest

from agent_eval_lab.calibrate.packet import (
    PACKET_FORMAT,
    RUBRIC_VERSION,
    build_packet,
    packet_from_jsonl,
    packet_to_jsonl,
)
from agent_eval_lab.records.trajectory import Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolCall,
    ToolCallTurn,
    ToolResultTurn,
    ToolSuccess,
)
from agent_eval_lab.tasks.schema import LlmJudgeSpec

SPEC = LlmJudgeSpec(rubric="Judge fidelity.", judge_model="m", scale=(1, 5))


def _fixture(fid, assistant):
    traj = Trajectory(
        turns=(
            MessageTurn(role="user", content="Close T-1."),
            ToolCallTurn(
                tool_calls=(
                    ToolCall(
                        call_id="c1",
                        name="update_ticket",
                        arguments={"ticket_id": "T-1", "status": "closed"},
                    ),
                )
            ),
            ToolResultTurn(call_id="c1", outcome=ToolSuccess(result={"ok": True})),
            MessageTurn(role="assistant", content=assistant),
        ),
        usage=Usage(prompt_tokens=0, completion_tokens=0, latency_s=0.0),
        run_index=0,
        stop_reason="completed",
    )
    return fid, traj


def test_build_packet_is_blind_and_ordered() -> None:
    fixtures = [_fixture("f2", "Done."), _fixture("f1", "Done and emailed.")]
    packet = build_packet(fixtures=fixtures, spec=SPEC, rubric="RUBRIC TEXT")
    assert packet.packet_format == PACKET_FORMAT
    assert packet.rubric_version == RUBRIC_VERSION
    assert packet.rubric == "RUBRIC TEXT"
    assert packet.annotator_id is None
    # fixed deterministic order = input order (authoring order), NOT sorted-by-id
    assert [i.fixture_id for i in packet.items] == ["f2", "f1"]
    # blind: every score is None, the digest carries no score and no intended label
    assert all(i.score is None for i in packet.items)
    assert "SCORE" not in packet.items[0].trajectory_digest
    assert "intended" not in packet.items[0].trajectory_digest.lower()


def test_packet_jsonl_round_trips() -> None:
    fixtures = [_fixture("f1", "Done.")]
    packet = build_packet(fixtures=fixtures, spec=SPEC, rubric="R")
    lines = packet_to_jsonl(packet)
    assert packet_from_jsonl(lines) == packet


def test_packet_jsonl_header_is_first_line() -> None:
    packet = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    header = json.loads(packet_to_jsonl(packet).splitlines()[0])
    assert header["packet_format"] == PACKET_FORMAT
    assert header["rubric_version"] == RUBRIC_VERSION


# Task 15: import_packet


def _filled(packet, scores, annotator):
    items = tuple(dataclasses.replace(i, score=s) for i, s in zip(packet.items, scores))
    return dataclasses.replace(packet, items=items, annotator_id=annotator)


def test_import_accepts_complete_filled_packet() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(
        fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")],
        spec=SPEC,
        rubric="R",
    )
    filled = _filled(blank, [5, 3], "alice")
    out = import_packet(packet_to_jsonl(filled), expected=blank)
    assert out.annotator_id == "alice"
    assert [i.score for i in out.items] == [5, 3]


def test_import_rejects_incomplete_packet() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(
        fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")],
        spec=SPEC,
        rubric="R",
    )
    partial = _filled(blank, [5, None], "alice")
    with pytest.raises(ValueError, match="unscored"):
        import_packet(packet_to_jsonl(partial), expected=blank)


def test_import_rejects_out_of_range_score() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    bad = _filled(blank, [9], "alice")
    with pytest.raises(ValueError, match="out of range"):
        import_packet(packet_to_jsonl(bad), expected=blank, scale=(1, 5))


def test_import_rejects_reordered_items() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(
        fixtures=[_fixture("f1", "Done."), _fixture("f2", "Done.")],
        spec=SPEC,
        rubric="R",
    )
    filled = _filled(blank, [5, 3], "alice")
    reordered = dataclasses.replace(filled, items=tuple(reversed(filled.items)))
    with pytest.raises(ValueError, match="item order"):
        import_packet(packet_to_jsonl(reordered), expected=blank)


def test_import_rejects_packet_format_mismatch() -> None:
    from agent_eval_lab.calibrate.packet import import_packet

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    filled = _filled(blank, [5], "alice")
    text = packet_to_jsonl(filled).replace(PACKET_FORMAT, "calib-packet-v0")
    with pytest.raises(ValueError, match="packet_format"):
        import_packet(text, expected=blank)


# Task 16: compute_agreement + render_agreement_report


def test_compute_agreement_binarizes_and_reports_kappa() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(
        fixtures=[_fixture(f"f{i}", "Done.") for i in range(4)], spec=SPEC, rubric="R"
    )
    # Annotator A: 5,5,3,3  -> faithful,faithful,unfaithful,unfaithful
    # Annotator B: 5,3,5,3  -> faithful,unfaithful,faithful,unfaithful
    a = _filled(blank, [5, 5, 3, 3], "A")
    b = _filled(blank, [5, 3, 5, 3], "B")
    report = compute_agreement(
        [a, b], threshold=4, scale=(1, 5), seed=11, n_resamples=200, alpha=0.05
    )
    assert report["binary_kappa"]["point"] == pytest.approx(0.0)  # chance-level 2x2
    assert "weighted_kappa" in report
    assert report["confusion_matrix"][("faithful", "faithful")] == 1
    assert report["n_items"] == 4


def test_compute_agreement_requires_two_packets() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    with pytest.raises(ValueError, match="two annotators"):
        compute_agreement(
            [_filled(blank, [5], "A")],
            threshold=4,
            scale=(1, 5),
            seed=1,
            n_resamples=10,
            alpha=0.05,
        )


# Fix 1: compute_agreement guards — unscored items and != 2 packets


def test_compute_agreement_rejects_more_than_two_packets() -> None:
    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(fixtures=[_fixture("f1", "Done.")], spec=SPEC, rubric="R")
    a = _filled(blank, [5], "A")
    b = _filled(blank, [5], "B")
    c = _filled(blank, [5], "C")
    with pytest.raises(ValueError, match="exactly 2"):
        compute_agreement(
            [a, b, c],
            threshold=4,
            scale=(1, 5),
            seed=1,
            n_resamples=10,
            alpha=0.05,
        )


def test_compute_agreement_rejects_unscored_items_in_first_packet() -> None:
    """An unscored (score=None) item must raise a structured ValueError naming the
    fixture_id — never silently compute with None or crash mid-comprehension."""
    import dataclasses

    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(
        fixtures=[_fixture("cf-01", "Done."), _fixture("cf-02", "Done.")],
        spec=SPEC,
        rubric="R",
    )
    # Packet A has one unscored item
    items_with_none = (
        dataclasses.replace(blank.items[0], score=None),
        dataclasses.replace(blank.items[1], score=3),
    )
    a = dataclasses.replace(blank, items=items_with_none, annotator_id="A")
    b = _filled(blank, [5, 3], "B")
    with pytest.raises(ValueError, match="cf-01"):
        compute_agreement(
            [a, b], threshold=4, scale=(1, 5), seed=1, n_resamples=10, alpha=0.05
        )


def test_compute_agreement_poisoned_kappa_two_none_items_rejected() -> None:
    """Two packets with matching None items must NOT compute agreement — the guard
    fires before binarize so None==None is never counted as agreement."""
    import dataclasses

    from agent_eval_lab.calibrate.packet import compute_agreement

    blank = build_packet(
        fixtures=[_fixture("cf-01", "Done."), _fixture("cf-02", "Done.")],
        spec=SPEC,
        rubric="R",
    )
    a = dataclasses.replace(
        blank,
        items=(
            dataclasses.replace(blank.items[0], score=None),
            dataclasses.replace(blank.items[1], score=None),
        ),
        annotator_id="A",
    )
    b = dataclasses.replace(
        blank,
        items=(
            dataclasses.replace(blank.items[0], score=None),
            dataclasses.replace(blank.items[1], score=None),
        ),
        annotator_id="B",
    )
    with pytest.raises(ValueError, match="unscored"):
        compute_agreement(
            [a, b], threshold=4, scale=(1, 5), seed=1, n_resamples=10, alpha=0.05
        )


def test_render_agreement_report_contains_kappa_and_ci() -> None:
    from agent_eval_lab.calibrate.packet import (
        compute_agreement,
        render_agreement_report,
    )

    blank = build_packet(
        fixtures=[_fixture(f"f{i}", "Done.") for i in range(4)], spec=SPEC, rubric="R"
    )
    a = _filled(blank, [5, 5, 3, 3], "A")
    b = _filled(blank, [5, 3, 5, 3], "B")
    md = render_agreement_report(
        compute_agreement(
            [a, b], threshold=4, scale=(1, 5), seed=11, n_resamples=200, alpha=0.05
        )
    )
    assert "Cohen" in md and "kappa" in md.lower()
    assert "CI" in md
    assert "Confusion matrix" in md
