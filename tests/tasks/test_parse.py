import pytest

from agent_eval_lab.tasks.parse import parse_task, verification_from_dict
from agent_eval_lab.tasks.schema import OutputMatchSpec, ToolCallMatchSpec

TASK_DATA = {
    "id": "ws-001",
    "capability": "tool_selection",
    "input": {
        "messages": [
            {
                "type": "message",
                "role": "system",
                "content": "You are a support agent.",
            },
            {
                "type": "message",
                "role": "user",
                "content": "Search the docs for 'refund policy'.",
            },
        ],
        "available_tools": ["search_docs", "create_ticket", "update_ticket"],
    },
    "verification": {
        "type": "tool_call_match",
        "expected_tool_calls": [
            {"name": "search_docs", "arguments": {"query": "refund policy"}}
        ],
        "match": "exact_sequence",
    },
    "metadata": {
        "split": "dev",
        "version": "1",
        "provenance": "hand_written",
        "world_template_id": "workspace-v1",
    },
    "initial_state": {"docs": {}, "tickets": {}},
}


def test_parse_task_builds_full_record() -> None:
    task = parse_task(TASK_DATA)

    assert task.id == "ws-001"
    assert task.capability == "tool_selection"
    assert len(task.input.messages) == 2
    assert task.input.available_tools == (
        "search_docs",
        "create_ticket",
        "update_ticket",
    )
    assert isinstance(task.verification, ToolCallMatchSpec)
    assert task.verification.expected_tool_calls[0].name == "search_docs"
    assert task.metadata.split == "dev"
    assert task.metadata.world_template_id == "workspace-v1"
    assert task.metadata.difficulty_knob is None
    assert task.initial_state == {"docs": {}, "tickets": {}}


def test_parse_task_rejects_bad_split() -> None:
    bad = {**TASK_DATA, "metadata": {**TASK_DATA["metadata"], "split": "test"}}

    with pytest.raises(ValueError, match="split"):
        parse_task(bad)


def test_parse_task_rejects_non_message_input_turns() -> None:
    bad_input = {
        **TASK_DATA["input"],
        "messages": [
            {
                "type": "tool_result",
                "call_id": "c1",
                "outcome": {"type": "success", "result": None},
            }
        ],
    }

    with pytest.raises(ValueError, match="message"):
        parse_task({**TASK_DATA, "input": bad_input})


def test_verification_from_dict_parses_output_match() -> None:
    spec = verification_from_dict(
        {"type": "output_match", "expected_output": "Done.", "normalizer": None}
    )

    assert isinstance(spec, OutputMatchSpec)
    assert spec.expected_output == "Done."
    assert spec.normalizer is None


def test_verification_from_dict_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="unknown verification type"):
        verification_from_dict({"type": "llm_judge", "rubric": "x"})


from agent_eval_lab.tasks.schema import (  # noqa: E402
    AllOf,
    FinalStateSpec,
    MaxToolCalls,
    NoToolCall,
    OnlyModifies,
    StateContains,
    StateEquals,
    TrajectorySpec,
)


def test_verification_from_dict_parses_final_state() -> None:
    spec = verification_from_dict(
        {
            "type": "final_state",
            "constraints": [
                {
                    "type": "state_equals",
                    "path": "tickets.T-1.status",
                    "expected": "closed",
                },
                {"type": "state_contains", "path": "docs.ids", "expected": "doc-1"},
            ],
        }
    )

    assert isinstance(spec, FinalStateSpec)
    assert isinstance(spec.constraints[0], StateEquals)
    assert spec.constraints[0].path == "tickets.T-1.status"
    assert isinstance(spec.constraints[1], StateContains)
    assert spec.constraints[1].expected == "doc-1"


def test_verification_from_dict_parses_trajectory() -> None:
    spec = verification_from_dict(
        {
            "type": "trajectory",
            "constraints": [
                {"type": "no_tool_call", "name": "delete_ticket"},
                {"type": "only_modifies", "paths": ["tickets.T-1"]},
                {"type": "max_tool_calls", "n": 3},
            ],
        }
    )

    assert isinstance(spec, TrajectorySpec)
    assert isinstance(spec.constraints[0], NoToolCall)
    assert isinstance(spec.constraints[1], OnlyModifies)
    assert spec.constraints[1].paths == ("tickets.T-1",)
    assert isinstance(spec.constraints[2], MaxToolCalls)
    assert spec.constraints[2].n == 3


def test_verification_from_dict_parses_all_of_recursively() -> None:
    spec = verification_from_dict(
        {
            "type": "all_of",
            "specs": [
                {"type": "output_match", "expected_output": "done"},
                {
                    "type": "all_of",
                    "specs": [{"type": "final_state", "constraints": []}],
                },
            ],
        }
    )

    assert isinstance(spec, AllOf)
    assert isinstance(spec.specs[1], AllOf)
    assert isinstance(spec.specs[1].specs[0], FinalStateSpec)


def test_verification_from_dict_rejects_unknown_state_constraint() -> None:
    with pytest.raises(ValueError, match="unknown state constraint"):
        verification_from_dict(
            {"type": "final_state", "constraints": [{"type": "state_gt"}]}
        )


def test_verification_from_dict_rejects_unknown_trajectory_constraint() -> None:
    with pytest.raises(ValueError, match="unknown trajectory constraint"):
        verification_from_dict(
            {"type": "trajectory", "constraints": [{"type": "min_tool_calls"}]}
        )


def test_verification_from_dict_rejects_unknown_match_mode() -> None:
    with pytest.raises(ValueError, match="unknown match mode"):
        verification_from_dict(
            {
                "type": "tool_call_match",
                "expected_tool_calls": [{"name": "f", "arguments": {}}],
                "match": "partial",
            }
        )


def test_metadata_max_steps_and_review_default_to_none() -> None:
    from agent_eval_lab.tasks.parse import _parse_metadata

    meta = _parse_metadata(
        {"split": "dev", "version": "2", "provenance": "hand_written"}
    )

    assert meta.max_steps is None
    assert meta.review is None


def test_metadata_reads_max_steps_and_review_when_present() -> None:
    from agent_eval_lab.tasks.parse import _parse_metadata

    meta = _parse_metadata(
        {
            "split": "dev",
            "version": "2",
            "provenance": "hand_written",
            "world_template_id": "workspace-v2",
            "max_steps": 10,
            "review": "passed:rubric-v1",
        }
    )

    assert meta.max_steps == 10
    assert meta.review == "passed:rubric-v1"
