"""Tests for the Factor V confined-execution sandbox (item 005).

Sections (in order):
  1. NodeFeedbackResult record + tail-aware renderer (Task 1)
  2. Pure seatbelt profile builder + Darwin/sandbox-exec probe (Task 2)
  3. make_authored_test_executor — fake run_fn wiring (Task 3)
  4. End-to-end V loop with a FAKE executor, CI-safe (Task 7)
  5. macOS-only integration test — ACTUALLY blocks the leak (Task 8)
"""

# ---------------------------------------------------------------------------
# Task 1: NodeFeedbackResult + tail-aware renderer
# ---------------------------------------------------------------------------

from agent_eval_lab.records.node_feedback import (
    FEEDBACK_SCHEMA_VERSION,
    NodeFeedbackResult,
    node_feedback_result_from_dict,
    node_feedback_result_to_dict,
    render_feedback_tail,
)


def test_node_feedback_result_round_trips() -> None:
    rec = NodeFeedbackResult(
        status="failed",
        exit_code=1,
        passed=2,
        failed=1,
        output="ok 1\nnot ok 2\n# fail 1\n",
    )
    back = node_feedback_result_from_dict(node_feedback_result_to_dict(rec))
    assert back == rec


def test_node_feedback_dict_carries_schema_version() -> None:
    rec = NodeFeedbackResult(
        status="passed", exit_code=0, passed=1, failed=0, output="# pass 1\n"
    )
    d = node_feedback_result_to_dict(rec)
    assert d["schema_version"] == FEEDBACK_SCHEMA_VERSION
    assert d["record"] == "node_feedback"


def test_render_feedback_tail_keeps_the_end_when_too_long() -> None:
    # 20000 lines; the failure summary is the LAST line. Tail-aware: it survives.
    body = "\n".join(f"ok {i}" for i in range(20000)) + "\n# fail 7 AT-THE-END\n"
    rendered = render_feedback_tail(body)
    assert "# fail 7 AT-THE-END" in rendered  # the END is kept (tail-aware)
    assert rendered.startswith("[head truncated]")  # marker at the FRONT
    assert len(rendered.encode("utf-8")) <= 8192 + len("[head truncated]\n")


def test_render_feedback_tail_passthrough_when_short() -> None:
    assert render_feedback_tail("# pass 3\n") == "# pass 3\n"


def test_render_feedback_tail_never_splits_a_multibyte_char() -> None:
    body = "é" * 9000  # 2 bytes each -> 18000 bytes, over the cap
    rendered = render_feedback_tail(body)
    # decodes cleanly (no half-character) and is tail-anchored
    assert rendered.encode("utf-8").decode("utf-8")
    assert rendered.endswith("é")
