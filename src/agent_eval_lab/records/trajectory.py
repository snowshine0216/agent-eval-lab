"""Run-time trajectory records emitted by the runner."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.turns import Turn


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
