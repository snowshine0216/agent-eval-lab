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


@dataclass(frozen=True, kw_only=True)
class StateEquals:
    type: Literal["state_equals"] = "state_equals"
    path: str
    expected: Any


@dataclass(frozen=True, kw_only=True)
class StateContains:
    type: Literal["state_contains"] = "state_contains"
    path: str
    expected: Any


StateConstraint = StateEquals | StateContains


@dataclass(frozen=True, kw_only=True)
class NoToolCall:
    type: Literal["no_tool_call"] = "no_tool_call"
    name: str


@dataclass(frozen=True, kw_only=True)
class OnlyModifies:
    type: Literal["only_modifies"] = "only_modifies"
    paths: tuple[str, ...]


@dataclass(frozen=True, kw_only=True)
class MaxToolCalls:
    type: Literal["max_tool_calls"] = "max_tool_calls"
    n: int


TrajectoryConstraint = NoToolCall | OnlyModifies | MaxToolCalls


@dataclass(frozen=True, kw_only=True)
class FinalStateSpec:
    type: Literal["final_state"] = "final_state"
    constraints: tuple[StateConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class TrajectorySpec:
    type: Literal["trajectory"] = "trajectory"
    constraints: tuple[TrajectoryConstraint, ...]


@dataclass(frozen=True, kw_only=True)
class AllOf:
    type: Literal["all_of"] = "all_of"
    specs: "tuple[VerificationSpec, ...]"


# Weeks 3-4 deterministic tier. LlmJudgeSpec (item 003) and ExecutionSpec
# (Weeks 5-6) extend this union later without breaking serialization.
VerificationSpec = (
    OutputMatchSpec | ToolCallMatchSpec | FinalStateSpec | TrajectorySpec | AllOf
)


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
    max_steps: int | None = None
    review: str | None = None


@dataclass(frozen=True, kw_only=True)
class Task:
    id: str
    capability: str
    input: TaskInput
    verification: VerificationSpec
    metadata: TaskMetadata
    initial_state: Mapping[str, Any] | None = None
