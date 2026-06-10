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
    """Run-time observed call. Carries the runtime-generated call_id."""

    call_id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
