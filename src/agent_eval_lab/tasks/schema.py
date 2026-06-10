"""Task records and the Weeks 1-2 VerificationSpec subset (spec §4.3-§4.4)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

from agent_eval_lab.records.turns import MessageTurn


@dataclass(frozen=True, kw_only=True)
class ExpectedToolCall:
    """Spec-time tool call; call_id is unknowable when authoring."""

    name: str
    arguments: Mapping[str, Any]


@dataclass(frozen=True, kw_only=True)
class OutputMatchSpec:
    type: Literal["output_match"] = "output_match"
    expected_output: str
    normalizer: str | None = None


@dataclass(frozen=True, kw_only=True)
class ToolCallMatchSpec:
    type: Literal["tool_call_match"] = "tool_call_match"
    expected_tool_calls: tuple[ExpectedToolCall, ...]
    match: Literal["exact_sequence", "multiset"] = "exact_sequence"


# Weeks 1-2 locked subset; FinalStateSpec/TrajectorySpec/AllOf/LlmJudgeSpec
# extend this union in Weeks 3-4 without breaking serialization.
VerificationSpec = OutputMatchSpec | ToolCallMatchSpec


@dataclass(frozen=True, kw_only=True)
class TaskInput:
    messages: tuple[MessageTurn, ...]
    available_tools: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class TaskMetadata:
    split: Literal["dev", "held_out"]
    version: str
    provenance: str
    world_template_id: str | None = None
    difficulty_knob: str | None = None


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = None
