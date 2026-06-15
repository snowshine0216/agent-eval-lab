"""Versioned V-feedback record + tail-aware renderer (ADR-0016, §9.7).

DISTINCT from records/execution.ExecutionResult: the oracle's record stays
head-truncated (truncate_output, ADR-0009) and byte-stable; V feedback is its
own versioned class rendered TAIL-aware (the node failure summary prints at the
END of a run, so the head is the disposable part). Nothing here imports or
changes truncate_output.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

FEEDBACK_SCHEMA_VERSION = 1
FEEDBACK_CAP_BYTES = 8192
HEAD_TRUNCATION_MARKER = "[head truncated]\n"

FeedbackStatus = Literal["passed", "failed", "error", "timeout"]


@dataclass(frozen=True, kw_only=True)
class NodeFeedbackResult:
    """One sandboxed authored-test run, rendered for the model (no wall-clock)."""

    status: FeedbackStatus
    exit_code: int
    passed: int
    failed: int
    output: str


def render_feedback_tail(text: str) -> str:
    """TAIL-truncate at FEEDBACK_CAP_BYTES of UTF-8, marker at the FRONT.

    The node failure summary prints at the END; keep the tail, drop the head. A
    multibyte character split at the cut is dropped, never half-recorded. Pure.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= FEEDBACK_CAP_BYTES:
        return text
    tail = encoded[-FEEDBACK_CAP_BYTES:].decode("utf-8", errors="ignore")
    return HEAD_TRUNCATION_MARKER + tail


def node_feedback_result_to_dict(result: NodeFeedbackResult) -> dict[str, Any]:
    return {
        "record": "node_feedback",
        "schema_version": FEEDBACK_SCHEMA_VERSION,
        "status": result.status,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "failed": result.failed,
        "output": result.output,
    }


def node_feedback_result_from_dict(data: Mapping[str, Any]) -> NodeFeedbackResult:
    return NodeFeedbackResult(
        status=data["status"],
        exit_code=data["exit_code"],
        passed=data["passed"],
        failed=data["failed"],
        output=data["output"],
    )
