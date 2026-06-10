"""Spec-time vs run-time tool-call records (design §4.1)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, kw_only=True)
class ExpectedToolCall:
    """Spec-time expected call. No call_id (unknowable when authoring)."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, kw_only=True)
class ToolCall:
    """Run-time observed call. Carries the runtime-generated call_id.

    arguments_parse_error is the raw payload (as text) when the provider emitted an
    arguments string that could not be parsed into a JSON object; it is None for a
    well-formed call. When set, `arguments` is empty and the call is graded
    malformed_call in stage 1 — independent of any tool schema.
    """

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    arguments_parse_error: str | None = None
