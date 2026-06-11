"""Run-time trajectory records emitted by the runner."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.turns import Turn

# The loop's empty-choices parse-failure literal: the provider envelope carried
# no completion at all, so the model under test never acted on the turn.
# Schema-adjacent (no record-shape change) and shared between runners/loop.py,
# which records it, and reports/classify.py, whose fc-v1 harness/agent
# parse-failure split keys on it (ADR-0013) — one constant, so the two sides
# cannot drift (item 004 grill Q3).
NO_CHOICES_ERROR = "no choices in provider response"


@dataclass(frozen=True, kw_only=True)
class ParseFailure:
    """Provider output that could not be parsed into a Turn (malformed call)."""

    type: Literal["parse_failure"] = "parse_failure"
    raw: str
    error: str


@dataclass(frozen=True, kw_only=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    latency_s: float


@dataclass(frozen=True, kw_only=True)
class Trajectory:
    turns: tuple[Turn, ...]
    usage: Usage
    run_index: int
    stop_reason: Literal["completed", "max_steps", "parse_failure"]
    parse_failure: ParseFailure | None = None
    final_state: Mapping[str, Any] | None = None
