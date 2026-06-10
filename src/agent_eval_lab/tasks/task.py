"""Task schema (design §4.4). Single-turn only this slice (no scripted_user)."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from agent_eval_lab.tasks.turns import MessageTurn
from agent_eval_lab.tasks.verification import VerificationSpec


@dataclass(frozen=True, kw_only=True)
class TaskInput:
    messages: tuple[MessageTurn, ...]
    available_tools: tuple[Mapping[str, Any], ...]  # JSON schemas


@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: str
    version: str
    provenance: str
    world_template_id: str
    difficulty_knob: str


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = field(default=None)
