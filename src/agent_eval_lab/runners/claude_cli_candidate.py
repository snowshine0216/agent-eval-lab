"""EDGE: run vanilla `claude -p` (Sonnet 4.6, no skills) as the F-task agent.

A baseline harness DISTINCT from the lab's chat-loop runner: Claude Code drives
its own loop with its native tools over a materialized copy of the pinned
web-dossier tree, then the held-out Node oracle grades the produced tree. Auth is
the session's OAuth/subscription (no per-token dollars; total_cost_usd is the
API-equivalent efficiency metric). See
docs/superpowers/specs/2026-06-16-claude-p-f-baseline-design.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass


class ClaudeResultParseError(ValueError):
    """`claude -p --output-format json` stdout could not be parsed into a result."""


@dataclass(frozen=True, kw_only=True)
class ClaudeRunMeta:
    prompt_tokens: int
    completion_tokens: int
    num_turns: int
    total_cost_usd: float
    is_error: bool


def parse_claude_result(stdout: str) -> ClaudeRunMeta:
    """Parse the single result object from `--output-format json`.

    Maps usage.input_tokens -> prompt_tokens, usage.output_tokens ->
    completion_tokens. Raises ClaudeResultParseError on malformed/incomplete JSON
    (the caller maps that to env-invalid, never a model FAIL)."""
    try:
        obj = json.loads(stdout)
        usage = obj["usage"]
        return ClaudeRunMeta(
            prompt_tokens=int(usage["input_tokens"]),
            completion_tokens=int(usage["output_tokens"]),
            num_turns=int(obj["num_turns"]),
            total_cost_usd=float(obj["total_cost_usd"]),
            is_error=bool(obj["is_error"]),
        )
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise ClaudeResultParseError(str(exc)) from exc
