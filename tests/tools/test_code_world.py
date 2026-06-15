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


def test_registry_is_exactly_the_five_tools_with_closed_schemas() -> None:
    assert sorted(CODE_WORLD_TOOLS) == [
        "list_files",
        "read_file",
        "run_tests",
        "str_replace",
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


# --- Finding 1: case-insensitive path collision ---


def test_write_file_rejects_case_insensitive_collision_with_existing_file() -> None:
    """a/Foo.py then a/foo.py must fail: distinct paths that casefold-match."""
    state0: dict = {"files": {}}
    state1, outcome1 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/Foo.py", "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome1, ToolSuccess)
    state2, outcome2 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/foo.py", "content": "x = 2\n"},
        state=state1,
    )
    assert state2 == state1, "state must not change on rejection"
    assert isinstance(outcome2, ToolFailure)
    assert "case" in outcome2.error.lower() or "collision" in outcome2.error.lower()


def test_write_file_allows_same_cased_overwrite() -> None:
    """Overwriting the exact same path must still succeed (not a casefold collision)."""
    state0: dict = {"files": {"a/Foo.py": "x = 1\n"}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/Foo.py", "content": "x = 2\n"},
        state=state0,
    )
    assert isinstance(outcome, ToolSuccess)
    assert outcome == ToolSuccess(result={"path": "a/Foo.py", "created": False})
    assert state1["files"]["a/Foo.py"] == "x = 2\n"


def test_write_file_rejects_case_insensitive_collision_at_root() -> None:
    """Root-level: README.md vs readme.md must be rejected."""
    state0: dict = {"files": {"README.md": "hello\n"}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "readme.md", "content": "world\n"},
        state=state0,
    )
    assert state1 == state0
    assert isinstance(outcome, ToolFailure)


# --- Finding 2: .junit.xml is harness-reserved ---


def test_write_file_rejects_junit_xml_reserved_path() -> None:
    """.junit.xml at root level must be rejected as harness-reserved."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": ".junit.xml", "content": "<xml/>\n"},
        state=state0,
    )
    assert state1 == state0
    assert isinstance(outcome, ToolFailure)
    assert "reserved" in outcome.error.lower() or "harness" in outcome.error.lower()


def test_write_file_allows_paths_that_merely_contain_junit_xml() -> None:
    """sub/.junit.xml is not the reserved root path — must succeed."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "sub/.junit.xml", "content": "<xml/>\n"},
        state=state0,
    )
    assert isinstance(outcome, ToolSuccess)


# --- Finding 002 (item 002): sitecustomize.py / usercustomize.py reservation ---


def test_write_file_rejects_root_sitecustomize_py() -> None:
    """Root-level sitecustomize.py is auto-imported by Python's site module at
    interpreter startup (before --noconftest / PYTEST_DISABLE_PLUGIN_AUTOLOAD
    take effect) when PYTHONPATH includes root — reserved by the harness."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "sitecustomize.py", "content": "import sys\n"},
        state=state0,
    )
    assert state1 == state0
    assert isinstance(outcome, ToolFailure)
    assert "reserved" in outcome.error.lower() or "harness" in outcome.error.lower()


def test_write_file_rejects_root_usercustomize_py() -> None:
    """Root-level usercustomize.py is auto-imported by Python's site module —
    same startup-hook attack vector as sitecustomize.py."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "usercustomize.py", "content": "import sys\n"},
        state=state0,
    )
    assert state1 == state0
    assert isinstance(outcome, ToolFailure)
    assert "reserved" in outcome.error.lower() or "harness" in outcome.error.lower()


def test_write_file_allows_nested_sitecustomize_py() -> None:
    """pkg/sitecustomize.py is not on PYTHONPATH root — must be allowed."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "pkg/sitecustomize.py", "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome, ToolSuccess)


def test_write_file_allows_nested_usercustomize_py() -> None:
    """pkg/usercustomize.py is not on PYTHONPATH root — must be allowed."""
    state0: dict = {"files": {}}
    state1, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "pkg/usercustomize.py", "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome, ToolSuccess)


# --- end Finding 002 ---


# --- end adversarial-review items ---


# --- Finding 001: Unicode-normalization and directory-segment collisions ---


def test_write_file_rejects_nfc_nfd_collision() -> None:
    """NFC café.py and NFD café.py are the same file on APFS."""
    state0: dict = {"files": {}}
    # NFC: "café.py" — U+00E9 is a precomposed character
    nfc_path = "café.py"
    # NFD: "café.py" — U+0065 + U+0301 (combining acute accent)
    nfd_path = "café.py"
    state1, outcome1 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": nfc_path, "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome1, ToolSuccess)
    state2, outcome2 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": nfd_path, "content": "x = 2\n"},
        state=state1,
    )
    assert state2 == state1, "state must not change on rejection"
    assert isinstance(outcome2, ToolFailure)
    assert "collision" in outcome2.error.lower()


def test_write_file_rejects_directory_segment_case_collision() -> None:
    """A/x.py then a/y.py: 'A' and 'a' collapse on APFS — must be rejected."""
    state0: dict = {"files": {}}
    state1, outcome1 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "A/x.py", "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome1, ToolSuccess)
    state2, outcome2 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/y.py", "content": "y = 2\n"},
        state=state1,
    )
    assert state2 == state1, "state must not change on rejection"
    assert isinstance(outcome2, ToolFailure)
    assert "collision" in outcome2.error.lower()


def test_write_file_allows_same_dir_distinct_files() -> None:
    """a/x.py then a/y.py in the same identically-spelled dir must succeed."""
    state0: dict = {"files": {}}
    state1, outcome1 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/x.py", "content": "x = 1\n"},
        state=state0,
    )
    assert isinstance(outcome1, ToolSuccess)
    state2, outcome2 = apply(
        registry=CODE_WORLD_TOOLS,
        name="write_file",
        arguments={"path": "a/y.py", "content": "y = 2\n"},
        state=state1,
    )
    assert isinstance(outcome2, ToolSuccess)
    assert "a/x.py" in state2["files"]
    assert "a/y.py" in state2["files"]


# --- end Finding 001 ---


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


def test_prefix_collision_is_the_public_shared_predicate() -> None:
    """Item 002: the single collision predicate, exported for the oracle
    overlay and the oracle-path parser (grill resolved decision 8)."""
    from agent_eval_lab.tools.code_world import prefix_collision

    assert prefix_collision("Tests/test_app.py", "tests/test_app.py") is True
    assert prefix_collision("tests/test_app.py", "tests/test_app.py") is False
    assert prefix_collision("tests/a.py", "tests/b.py") is False


# --- str_replace: targeted single-occurrence edit (F-domain repo fixes) ---


def test_str_replace_replaces_unique_occurrence_without_mutating_input() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="str_replace",
        arguments={
            "path": "calc.py",
            "old_str": "return a - b",
            "new_str": "return a + b",
        },
        state=STATE,
    )
    assert outcome == ToolSuccess(result={"path": "calc.py", "replaced": True})
    assert state["files"]["calc.py"] == "def add(a, b):\n    return a + b\n"
    # input state is never mutated (immutability contract)
    assert STATE["files"]["calc.py"] == "def add(a, b):\n    return a - b\n"


def test_str_replace_missing_file_is_tool_failure() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="str_replace",
        arguments={"path": "nope.py", "old_str": "a", "new_str": "b"},
        state=STATE,
    )
    assert state == STATE
    assert outcome == ToolFailure(error="no such file: nope.py")


def test_str_replace_absent_old_str_is_tool_failure() -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="str_replace",
        arguments={"path": "calc.py", "old_str": "not present", "new_str": "x"},
        state=STATE,
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)
    assert "not found" in outcome.error


def test_str_replace_ambiguous_old_str_is_tool_failure() -> None:
    multi = {"files": {"d.py": "x = 1\nx = 1\n"}}
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="str_replace",
        arguments={"path": "d.py", "old_str": "x = 1", "new_str": "x = 2"},
        state=multi,
    )
    assert state == multi
    assert isinstance(outcome, ToolFailure)
    assert "not unique" in outcome.error


@pytest.mark.parametrize("path", BAD_PATHS)
def test_str_replace_rejects_non_canonical_paths(path: str) -> None:
    state, outcome = apply(
        registry=CODE_WORLD_TOOLS,
        name="str_replace",
        arguments={"path": path, "old_str": "a", "new_str": "b"},
        state=STATE,
    )
    assert state == STATE
    assert isinstance(outcome, ToolFailure)
