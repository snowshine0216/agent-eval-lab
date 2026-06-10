"""Verification specs (tool-use subset) + open-union dispatch guard (design §4.3, §13)."""

from dataclasses import dataclass
from typing import Literal

from agent_eval_lab.tasks.tool_calls import ExpectedToolCall


@dataclass(frozen=True, kw_only=True)
class OutputMatchSpec:
    expected_output: str
    normalizer: str | None = None
    type: Literal["output_match"] = "output_match"


@dataclass(frozen=True, kw_only=True)
class ToolCallMatchSpec:
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"
    type: Literal["tool_call_match"] = "tool_call_match"


VerificationSpec = OutputMatchSpec | ToolCallMatchSpec

_IMPLEMENTED = frozenset({"output_match", "tool_call_match"})


class UnsupportedVerificationError(ValueError):
    """Raised when a VerificationSpec variant is not implemented this slice."""


def ensure_supported(spec_type: str) -> None:
    """Reject unimplemented (final_state/trajectory/execution/judge/all_of) variants."""
    if spec_type not in _IMPLEMENTED:
        raise UnsupportedVerificationError(
            f"verification type {spec_type!r} is not implemented in this slice"
        )
