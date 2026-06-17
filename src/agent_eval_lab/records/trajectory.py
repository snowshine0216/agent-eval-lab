"""Run-time trajectory records emitted by the runner."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from agent_eval_lab.records.env_health import EnvHealth
from agent_eval_lab.records.turns import Turn

# The loop's empty-choices parse-failure literal: the provider envelope carried
# no completion at all, so the model under test never acted on the turn.
# Schema-adjacent (no record-shape change) and shared between runners/loop.py,
# which records it, and reports/classify.py, whose fc-v1 harness/agent
# parse-failure split keys on it (ADR-0013) — one constant, so the two sides
# cannot drift (item 004 grill Q3).
NO_CHOICES_ERROR = "no choices in provider response"

# The loop's provider-request-failed literal: a /chat/completions call raised an
# httpx.HTTPError (a non-retryable HTTP status such as the SiliconFlow 400 that
# aborted a GLM-5.1 D-run, or a transport error that exhausted retries). The loop
# records it as a ParseFailure with this exact error (the status + a body snippet
# go in ParseFailure.raw — never an auth header) instead of crashing the run.
# Shared with reports/classify.py, whose fc-v3 chain maps it to
# harness_failure/provider_response, so the two sides cannot drift (mirrors
# NO_CHOICES_ERROR).
PROVIDER_ERROR = "provider request failed"


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
    stop_reason: Literal[
        # legacy values — never emitted by the censoring runner, kept parseable
        # for v1 artifacts (records+runner revision §7 / item 001 scope A)
        "completed",
        "max_steps",
        "parse_failure",
        # censoring-contract values emitted by the new runner
        "completed_natural",
        "safety_cap",
        "max_rounds",
        "env_unhealthy",
    ]
    schema_version: Literal["1", "2"] = "2"
    parse_failure: ParseFailure | None = None
    final_state: Mapping[str, Any] | None = None
    max_tokens: int | None = None
    """The completion budget requested for this run (explicit eval parameter).

    None for artifacts captured before fc-v2 (pre-explicit-budget runs); those
    artifacts keep classifying as before (no token_budget_exhausted for them).
    """
    rounds: int = 0
    """Model turns taken (each assistant reply, tool-call or final message)."""
    wall_time_s: float = 0.0
    """Cumulative wall-clock seconds across the run's provider calls."""
    total_cost_usd: float | None = None
    """API-equivalent dollar cost of this attempt, as reported by the provider.

    Set only by the claude-cli F-baseline runner (the OAuth/subscription session
    has no per-token dollars, so `claude -p`'s `total_cost_usd` is the efficiency
    metric). None for the token-metered B/D/M runners, whose cost is derived from
    token counts × TokenPrice, not reported per-run."""
    tool_call_counts: Mapping[str, int] = field(default_factory=dict)
    """Per-tool-name cumulative tool-call counts."""
    safety_cap_bound: bool = False
    """True iff the run stopped because it reached the safety cap (D35)."""
    max_rounds: int | None = None
    """The per-run turn budget in effect (model turns); None ⇒ unbounded (§A.2)."""
    safety_cap: int | None = None
    """The tool-call backstop in effect; recorded so an artifact proves its policy."""
    max_rounds_bound: bool = False
    """True iff the run stopped because it reached max_rounds (§A.2/§D.1)."""
    env_health: EnvHealth | None = None
    """Pre/post health-probe result; None for env-free (F-set) tasks (§18.5)."""
    run_uid: str | None = None
    """Per-run unique id. B/D: f"{condition_id}__{run_index:04d}" (§18.1); F is
    task-scoped f"{condition_id}__{task_id}__{run_index:04d}" so 12 task-arms
    sharing a condition's run space cannot collide (item 003 §B.2/§11.8)."""

    @classmethod
    def v1_compat(cls, mapping: Mapping[str, Any]) -> "Trajectory":
        """Hydrate a pre-revision artifact (no schema_version / new fields).

        Tags schema_version="1"; leaves stop_reason as-is (legacy values stay
        parseable); applies safe defaults for every field the revision added.
        Turns/usage/parse_failure hydration is delegated to serialize so the
        round-trip stays single-sourced — this method takes the ALREADY-parsed
        components and assembles a v1-tagged Trajectory.
        """
        return cls(
            turns=tuple(mapping["turns"]),
            usage=mapping["usage"],
            run_index=mapping["run_index"],
            stop_reason=mapping["stop_reason"],
            schema_version="1",
            parse_failure=mapping.get("parse_failure"),
            final_state=mapping.get("final_state"),
            max_tokens=mapping.get("max_tokens"),
        )
