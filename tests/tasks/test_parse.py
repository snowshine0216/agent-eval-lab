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
        verification_from_dict({"type": "bad_type", "rubric": "x"})


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


def test_parses_llm_judge_with_default_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict
    from agent_eval_lab.tasks.schema import LlmJudgeSpec

    spec = verification_from_dict(
        {"type": "llm_judge", "rubric": "Score fidelity.", "judge_model": "glm:m"}
    )

    assert spec == LlmJudgeSpec(
        rubric="Score fidelity.", judge_model="glm:m", scale=(1, 5)
    )


def test_parses_llm_judge_with_explicit_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict

    spec = verification_from_dict(
        {"type": "llm_judge", "rubric": "r", "judge_model": "m", "scale": [1, 7]}
    )

    assert spec.scale == (1, 7)


def test_llm_judge_rejects_bad_scale() -> None:
    from agent_eval_lab.tasks.parse import verification_from_dict

    for bad in ([5, 1], [1], [1, 2, 3], ["1", "5"]):
        with pytest.raises(ValueError, match="scale"):
            verification_from_dict(
                {"type": "llm_judge", "rubric": "r", "judge_model": "m", "scale": bad}
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


_ORACLE_TESTS = {
    "test_oracle_calc.py": (
        "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    ),
    "conftest.py": "# oracle helper modules are legitimate\n",
}


def test_verification_from_dict_parses_execution_spec() -> None:
    from agent_eval_lab.tasks.schema import ExecutionSpec

    spec = verification_from_dict(
        {"type": "execution", "held_out_tests": _ORACLE_TESTS, "timeout_s": 5}
    )

    assert spec == ExecutionSpec(held_out_tests=_ORACLE_TESTS, timeout_s=5.0)
    assert isinstance(spec.timeout_s, float)  # JSON int stored as float


def test_execution_spec_timeout_defaults_to_none() -> None:
    spec = verification_from_dict(
        {"type": "execution", "held_out_tests": _ORACLE_TESTS}
    )

    assert spec.timeout_s is None


def test_execution_task_row_parses_from_jsonl_shape() -> None:
    import json

    from agent_eval_lab.tasks.schema import ExecutionSpec

    row = json.loads(
        json.dumps(
            {
                **TASK_DATA,
                "verification": {
                    "type": "execution",
                    "held_out_tests": _ORACLE_TESTS,
                    "timeout_s": 5,
                },
                "initial_state": {"files": {"calc.py": "def add(a, b): ...\n"}},
            }
        )
    )

    task = parse_task(row)

    assert task.verification == ExecutionSpec(
        held_out_tests=_ORACLE_TESTS, timeout_s=5.0
    )


def test_execution_rejects_empty_held_out_tests() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        verification_from_dict({"type": "execution", "held_out_tests": {}})


@pytest.mark.parametrize(
    "path",
    ["/abs.py", "../escape.py", "a/../b.py", "a//b.py", ".", "a\\b.py", "bad\x00.py"],
)
def test_execution_rejects_non_canonical_oracle_paths(path: str) -> None:
    with pytest.raises(ValueError, match="held_out_tests"):
        verification_from_dict(
            {"type": "execution", "held_out_tests": {path: "x = 1\n"}}
        )


def test_execution_rejects_reserved_junit_path() -> None:
    with pytest.raises(ValueError, match="reserved"):
        verification_from_dict(
            {"type": "execution", "held_out_tests": {".junit.xml": "<xml/>"}}
        )


def test_execution_rejects_oracle_internal_prefix_collision() -> None:
    with pytest.raises(ValueError, match="canonical-prefix collision"):
        verification_from_dict(
            {
                "type": "execution",
                "held_out_tests": {
                    "tests/test_a.py": "x = 1\n",
                    "Tests/test_b.py": "y = 2\n",
                },
            }
        )


@pytest.mark.parametrize("timeout_s", [0, -1, 0.0, -0.5, True, False, "5"])
def test_execution_rejects_non_positive_or_non_numeric_timeout(timeout_s) -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        verification_from_dict(
            {
                "type": "execution",
                "held_out_tests": _ORACLE_TESTS,
                "timeout_s": timeout_s,
            }
        )
