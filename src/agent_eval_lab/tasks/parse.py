"""Pure parsing: JSON-shaped dicts -> Task records."""

from collections.abc import Mapping
from typing import Any

from agent_eval_lab.records.serialize import turn_from_dict
from agent_eval_lab.records.turns import MessageTurn, Turn
from agent_eval_lab.tasks.schema import (
    ExpectedToolCall,
    OutputMatchSpec,
    Task,
    TaskInput,
    TaskMetadata,
    ToolCallMatchSpec,
    VerificationSpec,
)

_SPLITS = ("dev", "held_out")
_MATCH_MODES = ("exact_sequence", "multiset")


def verification_from_dict(data: Mapping[str, Any]) -> VerificationSpec:
    kind = data["type"]
    if kind == "output_match":
        return OutputMatchSpec(
            expected_output=data["expected_output"],
            normalizer=data.get("normalizer"),
        )
    if kind == "tool_call_match":
        match = data.get("match", "exact_sequence")
        if match not in _MATCH_MODES:
            raise ValueError(f"unknown match mode: {match!r}")
        return ToolCallMatchSpec(
            expected_tool_calls=tuple(
                ExpectedToolCall(name=c["name"], arguments=c["arguments"])
                for c in data["expected_tool_calls"]
            ),
            match=match,
        )
    raise ValueError(f"unknown verification type: {kind!r}")


def _require_message(turn: Turn) -> MessageTurn:
    if not isinstance(turn, MessageTurn):
        raise ValueError(f"task input turns must be message turns, got {turn.type!r}")
    return turn


def _parse_messages(raw: list[Mapping[str, Any]]) -> tuple[MessageTurn, ...]:
    return tuple(_require_message(turn_from_dict(m)) for m in raw)


def _parse_metadata(data: Mapping[str, Any]) -> TaskMetadata:
    if data["split"] not in _SPLITS:
        raise ValueError(f"unknown split: {data['split']!r}")
    return TaskMetadata(
        split=data["split"],
        version=data["version"],
        provenance=data["provenance"],
        world_template_id=data.get("world_template_id"),
        difficulty_knob=data.get("difficulty_knob"),
    )


def parse_task(data: Mapping[str, Any]) -> Task:
    input_data = data["input"]
    return Task(
        id=data["id"],
        capability=data["capability"],
        input=TaskInput(
            messages=_parse_messages(input_data["messages"]),
            available_tools=tuple(input_data["available_tools"]),
        ),
        verification=verification_from_dict(data["verification"]),
        metadata=_parse_metadata(data["metadata"]),
        initial_state=data.get("initial_state"),
    )
