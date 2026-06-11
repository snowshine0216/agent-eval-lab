import pytest

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS, apply
from agent_eval_lab.tools.workspace import ToolDef

STATE = {
    "files": {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_calc.py": (
            "from calc import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n"
        ),
    }
}

BAD_PATHS = [
    "/abs.py",
    "../escape.py",
    "a/../b.py",
    "",
    ".",
    "./a.py",
    "a/./b.py",
    "a//b.py",
    "a/",
    "a\\b.py",
    "bad\x00.py",
]


def test_registry_is_exactly_the_four_tools_with_closed_schemas() -> None:
    assert sorted(CODE_WORLD_TOOLS) == [
        "list_files",
        "read_file",
        "run_tests",
        "write_file",
    ]
    for name, tool in CODE_WORLD_TOOLS.items():
        assert tool.name == name
        assert tool.parameters["additionalProperties"] is False


def test_read_file_returns_path_and_content() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="read_file",
        arguments={"path": "calc.py"},
        state=STATE,
    )
    assert state == STATE
    assert outcome == ToolSuccess(
        result={"path": "calc.py", "content": STATE["files"]["calc.py"]}
    )


def test_read_file_missing_path_is_tool_failure() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="read_file",
        arguments={"path": "nope.py"},
        state=STATE,
    )
    assert state == STATE
    assert outcome == ToolFailure(error="no such file: nope.py")


def test_list_files_returns_sorted_paths() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS, name="list_files", arguments={}, state=STATE
    )
    assert state == STATE
    assert outcome == ToolSuccess(result={"paths": ["calc.py", "tests/test_calc.py"]})


@pytest.mark.parametrize("path", BAD_PATHS)
def test_read_file_rejects_non_canonical_paths(path: str) -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="read_file",
        arguments={"path": path},
        state=STATE,
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)


def test_unknown_tool_is_tool_failure() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS, name="delete_file", arguments={}, state=STATE
    )
    assert state == STATE
    assert outcome == ToolFailure(error="unknown tool: delete_file")


def test_schema_violation_is_tool_failure() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS, name="read_file", arguments={}, state=STATE
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)
    assert outcome.error.startswith("schema violation")


def test_write_file_creates_new_file_without_mutating_input() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "notes.md", "content": "hello\n"},
        state=STATE,
    )
    assert outcome == ToolSuccess(result={"path": "notes.md", "created": True})
    assert state["files"]["notes.md"] == "hello\n"
    assert "notes.md" not in STATE["files"]


def test_write_file_overwrites_existing_file() -> None:
    fixed = "def add(a, b):\n    return a + b\n"
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "calc.py", "content": fixed},
        state=STATE,
    )
    assert outcome == ToolSuccess(result={"path": "calc.py", "created": False})
    assert state["files"]["calc.py"] == fixed
    assert STATE["files"]["calc.py"] == "def add(a, b):\n    return a - b\n"


@pytest.mark.parametrize("path", BAD_PATHS)
def test_write_file_rejects_non_canonical_paths(path: str) -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": path, "content": "x"},
        state=STATE,
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)


def test_write_file_rejects_directory_path_collision() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "tests", "content": "x"},
        state=STATE,
    )
    assert state == STATE
    assert outcome == ToolFailure(
        error="path collision: 'tests' is a directory in the tree"
    )


def test_write_file_rejects_file_prefix_collision() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "calc.py/extra.py", "content": "x"},
        state=STATE,
    )
    assert state == STATE
    assert outcome == ToolFailure(
        error="path collision: 'calc.py' is a file in the tree"
    )


def test_run_tests_returns_request_and_identical_state() -> None:
    state, request = apply(
        registry=CODE_WORLD_TOOLS, name="run_tests", arguments={}, state=STATE
    )
    assert state == STATE
    assert isinstance(request, ExecutionRequest)
    assert dict(request.files) == STATE["files"]


def test_run_tests_snapshot_survives_caller_mutation() -> None:
    files = {"a.py": "x = 1\n"}
    _, request = apply(
        registry=CODE_WORLD_TOOLS,
        name="run_tests",
        arguments={},
        state={"files": files},
    )
    files["b.py"] = "y = 2\n"
    assert dict(request.files) == {"a.py": "x = 1\n"}


def test_run_tests_rejects_unexpected_arguments() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="run_tests",
        arguments={"path": "tests"},
        state=STATE,
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)
    assert outcome.error.startswith("schema violation")


def test_registered_but_unimplemented_tool_raises_runtime_error() -> None:
    ghost = ToolDef(
        name="ghost",
        description="registered but unimplemented",
        parameters={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    )
    with pytest.raises(RuntimeError, match="misconfiguration"):
        apply(
            registry={**CODE_WORLD_TOOLS, "ghost": ghost},
            name="ghost",
            arguments={},
            state=STATE,
        )
