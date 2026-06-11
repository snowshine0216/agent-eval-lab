# Item 001 — Code-world + Execution Edge + Effect-Request Bridge: Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver the code-world (four pure tools over an in-memory file tree), the sandboxed pytest execution edge, and the effect-request bridge through which the runner loop fulfills `run_tests` — per `docs/2026-06-11-coding-agent-eval/items/001-spec.md`, ADR-0008, and ADR-0009.

**Architecture:** Functional core / imperative shell. `records/execution.py` (frozen bridge records + canonical output cap) and `tools/code_world.py` (pure `apply`; `run_tests` returns an `ExecutionRequest` in the outcome position) stay pure. All subprocess/filesystem I/O lives in `runners/pytest_edge.py` (materialize → pinned-interpreter pytest in a scrubbed env → JUnit XML parse → canonicalize → cleanup in `finally`) and in `runners/loop.py`, which gains two additive defaulted parameters (`apply_fn`, `executor`) and fulfills requests matched on type, never tool name.

**Tech Stack:** Python 3.11+ (project venv is 3.13.12), stdlib only for new runtime code (`subprocess`, `tempfile`, `xml.etree`, `os`, `signal`, `shutil`, `re`), pytest 9.0.3 (pinned via `uv.lock`), Hypothesis (dev), ruff (`E,F,I,UP`, line length 88). All commands run via `uv run`.

**Branch:** stay on `autodev/coding-agent-eval-feature`. Commit after every task. NEVER push — the orchestrator handles pushes.

**Already done — do NOT recreate:** `docs/adr/0008-mid-trajectory-effects-bridge-through-effect-requests.md`, `docs/adr/0009-recorded-execution-output-is-canonicalized-never-verbatim.md`, and the CONTEXT.md "Code-world & execution" cluster exist (commit `bcaa522`). Spec criterion 13 is satisfied; no plan task touches them.

**Baseline:** `uv run pytest` currently reports `363 passed`. Every task below must keep that baseline green.

**Pre-validated:** the final assembly of every code block in this plan was executed in a scratch worktree on this machine during planning: `435 passed` (zero warnings), `ruff check .` clean. The code is exact — type it verbatim; if a step's outcome differs from the stated expectation, suspect a transcription slip before suspecting the design.

**Empirically verified facts this plan relies on** (probed on this machine, pytest 9.0.3, scrubbed env, `-q --junitxml=<root>/.junit.xml -p no:cacheprovider`, `cwd=<root>`):
- Failing suite → exit 1; collection/import error → exit 2 (XML still written, one `<testcase classname="" name="test_broken">` with an `<error>` child); no tests → exit 5 (XML with zero testcases); skip → exit 0 with `skipped="1"` in XML.
- With `-q` there is no rootdir/header line; tracebacks for assertion failures use relative paths, but **collection-error output embeds the absolute temp root** — canonicalization is observable there.
- The summary line prints a timing token (`1 failed, 1 passed in 0.01s`, `no tests ran in 0.00s`).
- JUnit XML works under `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1` (junitxml is core pytest).
- `Path(tempfile.mkdtemp(...)).resolve()` pins one path spelling on macOS (`/private/var/...`), so a single string replacement canonicalizes all root occurrences.

---

## File map

| Path | Action | Responsibility |
|---|---|---|
| `src/agent_eval_lab/records/execution.py` | Create | Frozen `ExecutionRequest`/`ExecutionResult`/`TestCaseResult`, status literals, `OUTPUT_CAP_BYTES`/`TRUNCATION_MARKER`, `truncate_output`, dict round-trips. Pure, no I/O imports. |
| `src/agent_eval_lab/tools/code_world.py` | Create | `CODE_WORLD_TOOLS` registry (4 tools), canonical-path + collision validation, pure `apply` returning `tuple[State, ToolOutcome \| ExecutionRequest]`. |
| `src/agent_eval_lab/runners/pytest_edge.py` | Create | The execution edge: pure helpers (`canonicalize_output`, `parse_junit_xml`, `suite_status`) + effectful `materialize_tree`, `run_pytest`. |
| `src/agent_eval_lab/runners/loop.py` | Modify (full-file replacement shown in Task 12) | Additive `apply_fn`/`executor` params; fulfills `ExecutionRequest` as `ToolSuccess`; `RuntimeError` when no executor. |
| `tests/records/test_execution.py` | Create | Record shape, frozen-ness, round-trips, truncation. |
| `tests/tools/test_code_world.py` | Create | Unit tests (no mocks) for all four tools, path safety, collisions, guards. |
| `tests/tools/test_code_world_properties.py` | Create | Hypothesis: no-mutation + determinism properties. |
| `tests/runners/test_pytest_edge.py` | Create | Pure-helper unit tests + edge integration matrix + hermeticity + timeout + reproducibility. |
| `tests/runners/test_loop_effects.py` | Create | Loop fulfillment tests (kept separate from `tests/runners/test_loop.py`, which stays byte-identical to prove criterion 12's "existing tests pass unchanged"). |

Untouched (constraint): `records/turns.py`, `records/trajectory.py`, `records/serialize.py`, `tools/workspace.py`, `tests/runners/test_loop.py`.

Note on placement: the dict round-trip helpers live in `records/execution.py` (beside the records), not in `records/serialize.py` — keeps both modules under the ~200-line budget and avoids touching a frozen file. A serialized `ExecutionResult` is plain JSON data, so trajectories carrying it round-trip through the existing `serialize.py` unchanged.

---

### Task 1: Bridge records — `records/execution.py`

**Files:**
- Create: `tests/records/test_execution.py`
- Create: `src/agent_eval_lab/records/execution.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/records/test_execution.py` with exactly:

```python
import dataclasses
import json

import pytest

from agent_eval_lab.records.execution import (
    OUTPUT_CAP_BYTES,
    TRUNCATION_MARKER,
    ExecutionRequest,
    ExecutionResult,
    TestCaseResult,
    execution_request_from_dict,
    execution_request_to_dict,
    execution_result_from_dict,
    execution_result_to_dict,
    truncate_output,
)

RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=1,
    failed=1,
    errors=0,
    skipped=1,
    tests=(
        TestCaseResult(test_id="test_mod::test_a", status="failed"),
        TestCaseResult(test_id="test_mod::test_b", status="passed"),
        TestCaseResult(test_id="test_mod::test_c", status="skipped"),
    ),
    stdout="1 failed, 1 passed, 1 skipped in <duration>",
    stderr="",
)


def test_execution_request_round_trips() -> None:
    request = ExecutionRequest(
        files={"a.py": "x = 1\n", "test_a.py": "import a\n"}
    )
    assert execution_request_from_dict(execution_request_to_dict(request)) == (
        request
    )


def test_execution_result_round_trips() -> None:
    assert execution_result_from_dict(execution_result_to_dict(RESULT)) == RESULT


def test_execution_result_dict_is_json_shaped() -> None:
    data = execution_result_to_dict(RESULT)
    assert json.loads(json.dumps(data)) == data


def test_execution_result_dict_has_exact_keys_no_duration() -> None:
    assert sorted(execution_result_to_dict(RESULT)) == [
        "errors",
        "exit_code",
        "failed",
        "passed",
        "skipped",
        "status",
        "stderr",
        "stdout",
        "tests",
    ]


def test_records_are_frozen() -> None:
    request = ExecutionRequest(files={})
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.files = {}  # type: ignore[misc]


def test_truncate_output_passes_short_text_through() -> None:
    assert truncate_output("short") == "short"


def test_truncate_output_keeps_head_and_appends_marker() -> None:
    text = "x" * (OUTPUT_CAP_BYTES + 100)
    assert truncate_output(text) == "x" * OUTPUT_CAP_BYTES + TRUNCATION_MARKER


def test_truncate_output_never_splits_a_multibyte_char() -> None:
    text = "€" * OUTPUT_CAP_BYTES  # 3 UTF-8 bytes each — far over the cap
    truncated = truncate_output(text)
    assert truncated.endswith(TRUNCATION_MARKER)
    body = truncated.removesuffix(TRUNCATION_MARKER)
    assert body == "€" * (OUTPUT_CAP_BYTES // 3)
```

- [ ] **Step 1.2: Run the tests to verify they fail**

Run: `uv run pytest tests/records/test_execution.py`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'agent_eval_lab.records.execution'`.

- [ ] **Step 1.3: Write the implementation**

Create `src/agent_eval_lab/records/execution.py` with exactly:

```python
"""Effect-request bridge records for code-world execution (ADR-0008/0009).

ExecutionRequest is what pure `apply` returns for `run_tests` (the
effect-request: a frozen file-tree snapshot, nothing else — timeout and
interpreter are edge policy). ExecutionResult is the deterministic record
the execution edge produces; the loop records it as ToolSuccess.result.
Wall-clock duration is deliberately absent (the one nondeterministic
observable), and recorded output is canonicalized, never verbatim.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal

OUTPUT_CAP_BYTES = 8192
TRUNCATION_MARKER = "\n[truncated]"

SuiteStatus = Literal["passed", "failed", "error", "timeout", "no_tests"]
TestStatus = Literal["passed", "failed", "error", "skipped"]


@dataclass(frozen=True, kw_only=True)
class ExecutionRequest:
    """Frozen snapshot of the file tree to run tests over; nothing else."""

    files: Mapping[str, str]


@dataclass(frozen=True, kw_only=True)
class TestCaseResult:
    """One per-test entry; test_id is `classname::name` from the JUnit XML."""

    __test__ = False  # tell pytest this record is not a test class

    test_id: str
    status: TestStatus


@dataclass(frozen=True, kw_only=True)
class ExecutionResult:
    """Deterministic record of one sandboxed pytest run (no wall-clock)."""

    status: SuiteStatus
    exit_code: int
    passed: int
    failed: int
    errors: int
    skipped: int
    tests: tuple[TestCaseResult, ...]
    stdout: str
    stderr: str


def truncate_output(text: str) -> str:
    """Head-truncate at OUTPUT_CAP_BYTES of UTF-8, with an explicit marker.

    A multibyte character split at the cap is dropped, never half-recorded.
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= OUTPUT_CAP_BYTES:
        return text
    head = encoded[:OUTPUT_CAP_BYTES].decode("utf-8", errors="ignore")
    return head + TRUNCATION_MARKER


def execution_request_to_dict(request: ExecutionRequest) -> dict[str, Any]:
    return {"files": dict(request.files)}


def execution_request_from_dict(data: Mapping[str, Any]) -> ExecutionRequest:
    return ExecutionRequest(files=dict(data["files"]))


def execution_result_to_dict(result: ExecutionResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "exit_code": result.exit_code,
        "passed": result.passed,
        "failed": result.failed,
        "errors": result.errors,
        "skipped": result.skipped,
        "tests": [
            {"test_id": case.test_id, "status": case.status}
            for case in result.tests
        ],
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def execution_result_from_dict(data: Mapping[str, Any]) -> ExecutionResult:
    return ExecutionResult(
        status=data["status"],
        exit_code=data["exit_code"],
        passed=data["passed"],
        failed=data["failed"],
        errors=data["errors"],
        skipped=data["skipped"],
        tests=tuple(
            TestCaseResult(test_id=case["test_id"], status=case["status"])
            for case in data["tests"]
        ),
        stdout=data["stdout"],
        stderr=data["stderr"],
    )
```

- [ ] **Step 1.4: Run the tests to verify they pass**

Run: `uv run pytest tests/records/test_execution.py`
Expected: `8 passed`.

- [ ] **Step 1.5: Commit**

```bash
git add tests/records/test_execution.py src/agent_eval_lab/records/execution.py
git commit -m "feat(records): execution bridge records + canonical output cap (ADR-0008/0009)"
```

---

### Task 2: code-world registry, `apply`, `read_file`, `list_files`, canonical paths

**Files:**
- Create: `tests/tools/test_code_world.py`
- Create: `src/agent_eval_lab/tools/code_world.py`

- [ ] **Step 2.1: Write the failing tests**

Create `tests/tools/test_code_world.py` with exactly:

```python
import pytest

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.turns import ToolFailure, ToolSuccess
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS, apply
from agent_eval_lab.tools.workspace import ToolDef

STATE = {
    "files": {
        "calc.py": "def add(a, b):\n    return a - b\n",
        "tests/test_calc.py": (
            "from calc import add\n"
            "\n"
            "\n"
            "def test_add():\n"
            "    assert add(1, 2) == 3\n"
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
    assert outcome == ToolSuccess(
        result={"paths": ["calc.py", "tests/test_calc.py"]}
    )


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
```

(`ToolDef` and `ExecutionRequest` imports are used by tests appended in Tasks 3-4; they stay in place now so the import block never changes again.)

- [ ] **Step 2.2: Run the tests to verify they fail**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'agent_eval_lab.tools.code_world'`.

- [ ] **Step 2.3: Write the implementation**

Create `src/agent_eval_lab/tools/code_world.py` with exactly:

```python
"""code-world: pure tools over an immutable file tree (ADR-0008).

State shape: {"files": {posix-relative-path: text-content}}. The editing
tools return a ToolOutcome; `run_tests` returns an ExecutionRequest in the
outcome position — the effect-request the runner loop fulfills at the
execution edge. This module performs no I/O. Path canonical-form and
collision rules make every reachable state materializable by construction.
"""

from collections.abc import Callable, Mapping
from typing import Any

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.turns import ToolFailure, ToolOutcome, ToolSuccess
from agent_eval_lab.tools.validation import validate_args
from agent_eval_lab.tools.workspace import ToolDef

State = Mapping[str, Any]

_PATH_SCHEMA = {"type": "string", "minLength": 1}
_NO_ARGS = {
    "type": "object",
    "properties": {},
    "required": [],
    "additionalProperties": False,
}

CODE_WORLD_TOOLS: Mapping[str, ToolDef] = {
    "read_file": ToolDef(
        name="read_file",
        description="Read the full text content of a file in the tree.",
        parameters={
            "type": "object",
            "properties": {"path": _PATH_SCHEMA},
            "required": ["path"],
            "additionalProperties": False,
        },
    ),
    "write_file": ToolDef(
        name="write_file",
        description=(
            "Create a file, or fully overwrite an existing one, with the "
            "given text content."
        ),
        parameters={
            "type": "object",
            "properties": {
                "path": _PATH_SCHEMA,
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    ),
    "list_files": ToolDef(
        name="list_files",
        description="List every file path in the tree, sorted.",
        parameters=_NO_ARGS,
    ),
    "run_tests": ToolDef(
        name="run_tests",
        description=(
            "Run pytest over every visible test in the tree; returns "
            "structured per-test results."
        ),
        parameters=_NO_ARGS,
    ),
}


def path_error(path: str) -> str | None:
    """Reject any spelling that is not canonical POSIX-relative form."""
    if "\\" in path or "\x00" in path:
        return f"invalid path {path!r}: backslash and NUL are forbidden"
    if any(segment in ("", ".", "..") for segment in path.split("/")):
        return f"invalid path {path!r}: not canonical POSIX-relative form"
    return None


def _files(state: State) -> Mapping[str, str]:
    return state.get("files", {})


def _read_file(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    path = args["path"]
    error = path_error(path)
    if error is not None:
        return state, ToolFailure(error=error)
    content = _files(state).get(path)
    if content is None:
        return state, ToolFailure(error=f"no such file: {path}")
    return state, ToolSuccess(result={"path": path, "content": content})


def _list_files(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    return state, ToolSuccess(result={"paths": sorted(_files(state))})


ToolImpl = Callable[
    [Mapping[str, Any], State], tuple[State, ToolOutcome | ExecutionRequest]
]

_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "list_files": _list_files,
}


def apply(
    *,
    registry: Mapping[str, ToolDef],
    name: str,
    arguments: Mapping[str, Any],
    state: State,
) -> tuple[State, ToolOutcome | ExecutionRequest]:
    """Pure tool application; `run_tests` yields an effect-request (ADR-0008)."""
    tool = registry.get(name)
    if tool is None:
        return state, ToolFailure(error=f"unknown tool: {name}")
    error = validate_args(tool.parameters, arguments)
    if error is not None:
        return state, ToolFailure(error=f"schema violation: {error}")
    impl = _IMPLS.get(name)
    if impl is None:
        raise RuntimeError(
            f"harness misconfiguration: tool {name!r} is registered but has no "
            "implementation"
        )
    return impl(arguments, state)
```

(`write_file` and `run_tests` are registered but intentionally unimplemented until Tasks 3-4 — `apply`'s RuntimeError guard covers them, mirroring `workspace.apply`. No Task-2 test calls them.)

- [ ] **Step 2.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: `17 passed` (6 named tests + 11 parametrized path cases), no warnings (`TestCaseResult` declares `__test__ = False`).

- [ ] **Step 2.5: Commit**

```bash
git add tests/tools/test_code_world.py src/agent_eval_lab/tools/code_world.py
git commit -m "feat(tools): code-world registry, read_file/list_files, canonical path rule"
```

---

### Task 3: `write_file` with prefix-collision rules

**Files:**
- Modify: `tests/tools/test_code_world.py` (append)
- Modify: `src/agent_eval_lab/tools/code_world.py`

- [ ] **Step 3.1: Append the failing tests**

Append to the end of `tests/tools/test_code_world.py`:

```python
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
```

- [ ] **Step 3.2: Run the tests to verify they fail**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: FAIL — the new `write_file` tests error with `RuntimeError: harness misconfiguration: tool 'write_file' is registered but has no implementation`; the 17 Task-2 tests still pass.

- [ ] **Step 3.3: Implement `write_file`**

In `src/agent_eval_lab/tools/code_world.py`, replace exactly this block:

```python
def _files(state: State) -> Mapping[str, str]:
    return state.get("files", {})
```

with:

```python
def _files(state: State) -> Mapping[str, str]:
    return state.get("files", {})


def _ancestors(path: str) -> tuple[str, ...]:
    segments = path.split("/")
    return tuple("/".join(segments[:i]) for i in range(1, len(segments)))


def _collision_error(path: str, files: Mapping[str, str]) -> str | None:
    """Reject file/directory prefix collisions in both directions."""
    if any(existing.startswith(path + "/") for existing in files):
        return f"path collision: {path!r} is a directory in the tree"
    clash = next((p for p in _ancestors(path) if p in files), None)
    if clash is None:
        return None
    return f"path collision: {clash!r} is a file in the tree"
```

Then replace exactly this block:

```python
def _list_files(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    return state, ToolSuccess(result={"paths": sorted(_files(state))})
```

with:

```python
def _write_file(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    path = args["path"]
    files = _files(state)
    error = path_error(path) or _collision_error(path, files)
    if error is not None:
        return state, ToolFailure(error=error)
    created = path not in files
    new_state = {**state, "files": {**files, path: args["content"]}}
    return new_state, ToolSuccess(result={"path": path, "created": created})


def _list_files(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    return state, ToolSuccess(result={"paths": sorted(_files(state))})
```

Then replace exactly this block:

```python
_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "list_files": _list_files,
}
```

with:

```python
_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "write_file": _write_file,
    "list_files": _list_files,
}
```

- [ ] **Step 3.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: `32 passed`.

- [ ] **Step 3.5: Commit**

```bash
git add tests/tools/test_code_world.py src/agent_eval_lab/tools/code_world.py
git commit -m "feat(tools): code-world write_file with bidirectional prefix-collision rule"
```

---

### Task 4: `run_tests` effect-request + guards

**Files:**
- Modify: `tests/tools/test_code_world.py` (append)
- Modify: `src/agent_eval_lab/tools/code_world.py`

- [ ] **Step 4.1: Append the failing tests**

Append to the end of `tests/tools/test_code_world.py`:

```python
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
```

- [ ] **Step 4.2: Run the tests to verify they fail**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: FAIL — `test_run_tests_returns_request_and_identical_state` and `test_run_tests_snapshot_survives_caller_mutation` error with `RuntimeError: harness misconfiguration: tool 'run_tests' ...`; the other two new tests pass (they exercise validation and the guard); 32 prior tests still pass.

- [ ] **Step 4.3: Implement `run_tests`**

In `src/agent_eval_lab/tools/code_world.py`, replace exactly this block:

```python
ToolImpl = Callable[
```

with:

```python
def _run_tests(
    args: Mapping[str, Any], state: State
) -> tuple[State, ExecutionRequest]:
    """Read-only over the tree: identical state + a frozen snapshot request."""
    return state, ExecutionRequest(files={**_files(state)})


ToolImpl = Callable[
```

Then replace exactly this block:

```python
_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "write_file": _write_file,
    "list_files": _list_files,
}
```

with:

```python
_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "write_file": _write_file,
    "list_files": _list_files,
    "run_tests": _run_tests,
}
```

- [ ] **Step 4.4: Run the tests to verify they pass**

Run: `uv run pytest tests/tools/test_code_world.py`
Expected: `36 passed`.

- [ ] **Step 4.5: Commit**

```bash
git add tests/tools/test_code_world.py src/agent_eval_lab/tools/code_world.py
git commit -m "feat(tools): run_tests returns ExecutionRequest effect-request (ADR-0008)"
```

---

### Task 5: Purity and determinism properties (Hypothesis)

**Files:**
- Create: `tests/tools/test_code_world_properties.py`

These properties verify behavior already specified by Tasks 2-4's unit tests (criterion 2), so they are expected GREEN on arrival. If any property fails, STOP and fix the tool bug — never weaken the property.

- [ ] **Step 5.1: Write the property tests**

Create `tests/tools/test_code_world_properties.py` with exactly:

```python
import copy

from hypothesis import given
from hypothesis import strategies as st

from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS, apply

_SEGMENTS = st.text(alphabet="abcdefgh", min_size=1, max_size=6)
_PATHS = st.lists(_SEGMENTS, min_size=1, max_size=3).map("/".join)
_CONTENTS = st.text(max_size=50)
_TREES = st.dictionaries(_PATHS, _CONTENTS, max_size=4)


def _calls(path: str, content: str) -> tuple[tuple[str, dict], ...]:
    return (
        ("read_file", {"path": path}),
        ("write_file", {"path": path, "content": content}),
        ("list_files", {}),
        ("run_tests", {}),
    )


@given(tree=_TREES, path=_PATHS, content=_CONTENTS)
def test_apply_never_mutates_the_input_state(
    tree: dict[str, str], path: str, content: str
) -> None:
    state = {"files": tree}
    snapshot = copy.deepcopy(state)
    for name, arguments in _calls(path, content):
        apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        assert state == snapshot


@given(tree=_TREES, path=_PATHS, content=_CONTENTS)
def test_apply_is_deterministic(
    tree: dict[str, str], path: str, content: str
) -> None:
    state = {"files": tree}
    for name, arguments in _calls(path, content):
        first = apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        second = apply(
            registry=CODE_WORLD_TOOLS, name=name, arguments=arguments, state=state
        )
        assert first == second
```

(Generated trees may legitimately contain file/dir collisions like `{"a": ..., "a/b": ...}` — the tools must answer them with a deterministic `ToolFailure`, which both properties cover.)

- [ ] **Step 5.2: Run the property tests**

Run: `uv run pytest tests/tools/test_code_world_properties.py`
Expected: `2 passed`.

- [ ] **Step 5.3: Commit**

```bash
git add tests/tools/test_code_world_properties.py
git commit -m "test(tools): code-world no-mutation + determinism properties"
```

---

### Task 6: Execution edge pure helpers

**Files:**
- Create: `tests/runners/test_pytest_edge.py`
- Create: `src/agent_eval_lab/runners/pytest_edge.py`

- [ ] **Step 6.1: Write the failing tests**

Create `tests/runners/test_pytest_edge.py` with exactly:

```python
"""Execution edge: pure helpers + sandboxed pytest integration (ADR-0009)."""

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    parse_junit_xml,
    suite_status,
)

_JUNIT_XML = """<?xml version="1.0" encoding="utf-8"?>
<testsuites name="pytest tests">
<testsuite name="pytest" errors="0" failures="1" skipped="1" tests="3">
<testcase classname="test_calc" name="test_zero" time="0.001" />
<testcase classname="test_calc" name="test_add" time="0.001">
<failure message="assert -1 == 3">trace</failure>
</testcase>
<testcase classname="test_calc" name="test_later" time="0.000">
<skipped type="pytest.skip" message="later">reason</skipped>
</testcase>
</testsuite>
</testsuites>
"""


def test_canonicalize_output_replaces_root_and_timing_token() -> None:
    raw = (
        "ImportError in '/tmp/agent-eval-sandbox-x1/test_a.py'\n"
        "1 failed, 1 passed in 0.01s\n"
    )
    expected = (
        "ImportError in '<sandbox>/test_a.py'\n"
        "1 failed, 1 passed in <duration>\n"
    )
    assert canonicalize_output(raw, "/tmp/agent-eval-sandbox-x1") == expected


def test_canonicalize_output_normalizes_no_tests_summary() -> None:
    assert (
        canonicalize_output("no tests ran in 0.00s", "/r")
        == "no tests ran in <duration>"
    )


def test_parse_junit_xml_sorts_by_test_id_and_maps_statuses() -> None:
    assert parse_junit_xml(_JUNIT_XML) == (
        TestCaseResult(test_id="test_calc::test_add", status="failed"),
        TestCaseResult(test_id="test_calc::test_later", status="skipped"),
        TestCaseResult(test_id="test_calc::test_zero", status="passed"),
    )


@pytest.mark.parametrize(
    ("exit_code", "status"),
    [
        (0, "passed"),
        (1, "failed"),
        (2, "error"),
        (3, "error"),
        (4, "error"),
        (5, "no_tests"),
    ],
)
def test_suite_status_classifies_pytest_exit_codes(
    exit_code: int, status: str
) -> None:
    assert suite_status(exit_code) == status
```

- [ ] **Step 6.2: Run the tests to verify they fail**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: FAIL — collection error, `ModuleNotFoundError: No module named 'agent_eval_lab.runners.pytest_edge'`.

- [ ] **Step 6.3: Write the pure helpers**

Create `src/agent_eval_lab/runners/pytest_edge.py` with exactly:

```python
"""EDGE: the sandboxed pytest execution boundary (ADR-0008, ADR-0009).

The single place subprocess/filesystem I/O happens for code-world:
materialize the file tree into a fresh temp dir, run pinned-interpreter
(`sys.executable`) pytest in a scrubbed from-scratch environment under a
hard timeout, parse the JUnit XML, canonicalize the output, clean up in a
`finally`.

Known limitation (documented, restated by item 004): no kernel-level
network isolation on macOS without containers — mitigated by the env scrub
(no proxy vars), the tight default timeout, and the item-003 rubric banning
network-touching tasks. On timeout, partial output is discarded (it is
timing-dependent, hence nondeterministic): the record carries empty streams
and exit code -9 (the SIGKILL convention).
"""

import re
import xml.etree.ElementTree as ET

from agent_eval_lab.records.execution import (
    SuiteStatus,
    TestCaseResult,
    TestStatus,
)

SANDBOX_PLACEHOLDER = "<sandbox>"
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")


def canonicalize_output(text: str, root: str) -> str:
    """Replace the sandbox root and pytest timing token (ADR-0009). Pure."""
    return _TIMING_TOKEN.sub(
        "in <duration>", text.replace(root, SANDBOX_PLACEHOLDER)
    )


def _case_status(case: ET.Element) -> TestStatus:
    if case.find("failure") is not None:
        return "failed"
    if case.find("error") is not None:
        return "error"
    if case.find("skipped") is not None:
        return "skipped"
    return "passed"


def parse_junit_xml(xml_text: str) -> tuple[TestCaseResult, ...]:
    """Extract per-test entries sorted by `classname::name`. Pure."""
    cases = (
        TestCaseResult(
            test_id=f"{case.get('classname', '')}::{case.get('name', '')}",
            status=_case_status(case),
        )
        for case in ET.fromstring(xml_text).iter("testcase")
    )
    return tuple(sorted(cases, key=lambda case: case.test_id))


def suite_status(exit_code: int) -> SuiteStatus:
    """Pytest exit-code classification: 0/1/5 named; 2-4 (and rest) error."""
    if exit_code == 0:
        return "passed"
    if exit_code == 1:
        return "failed"
    if exit_code == 5:
        return "no_tests"
    return "error"
```

- [ ] **Step 6.4: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `9 passed`.

- [ ] **Step 6.5: Commit**

```bash
git add tests/runners/test_pytest_edge.py src/agent_eval_lab/runners/pytest_edge.py
git commit -m "feat(runners): pytest edge pure helpers — canonicalize, junit parse, exit classes"
```

---

### Task 7: Sandbox materializer with outside-root defense

**Files:**
- Modify: `tests/runners/test_pytest_edge.py`
- Modify: `src/agent_eval_lab/runners/pytest_edge.py`

- [ ] **Step 7.1: Update the test imports and append the failing tests**

In `tests/runners/test_pytest_edge.py`, replace exactly this block:

```python
import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    parse_junit_xml,
    suite_status,
)
```

with:

```python
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    materialize_tree,
    parse_junit_xml,
    suite_status,
)
```

Then append to the end of the file:

```python
def test_materialize_tree_writes_sorted_nested_utf8(tmp_path: Path) -> None:
    materialize_tree(
        {"pkg/mod.py": "x = 'é'\n", "test_mod.py": "import pkg.mod\n"},
        tmp_path,
    )
    written = tmp_path / "pkg" / "mod.py"
    assert written.read_text(encoding="utf-8") == "x = 'é'\n"
    assert (tmp_path / "test_mod.py").read_text(encoding="utf-8") == (
        "import pkg.mod\n"
    )


def test_materialize_tree_refuses_escape_outside_root(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="outside sandbox"):
        materialize_tree({"../escape.py": "x = 1\n"}, tmp_path)
```

- [ ] **Step 7.2: Run the tests to verify they fail**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: FAIL — collection error, `ImportError: cannot import name 'materialize_tree'`.

- [ ] **Step 7.3: Implement the materializer**

In `src/agent_eval_lab/runners/pytest_edge.py`, replace exactly this block:

```python
import re
import xml.etree.ElementTree as ET
```

with:

```python
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
```

Then append to the end of the file:

```python
def materialize_tree(files: Mapping[str, str], root: Path) -> None:
    """Write the tree under root: sorted order, parents created, UTF-8.

    Defense in depth: refuses any resolved target outside root, even though
    the pure tools already reject non-canonical paths.
    """
    resolved_root = root.resolve()
    for path in sorted(files):
        target = (resolved_root / path).resolve()
        if not target.is_relative_to(resolved_root):
            raise RuntimeError(
                f"refusing to materialize outside sandbox: {path!r}"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[path], encoding="utf-8")
```

- [ ] **Step 7.4: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `11 passed`.

- [ ] **Step 7.5: Commit**

```bash
git add tests/runners/test_pytest_edge.py src/agent_eval_lab/runners/pytest_edge.py
git commit -m "feat(runners): sandbox materializer with outside-root defense"
```

---

### Task 8: `run_pytest` — hermetic sandboxed execution

**Files:**
- Modify: `tests/runners/test_pytest_edge.py`
- Modify: `src/agent_eval_lab/runners/pytest_edge.py`

- [ ] **Step 8.1: Update the test imports and append the failing tests**

In `tests/runners/test_pytest_edge.py`, replace exactly this block:

```python
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    materialize_tree,
    parse_junit_xml,
    suite_status,
)
```

with:

```python
import tempfile
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import TestCaseResult
from agent_eval_lab.runners.pytest_edge import (
    canonicalize_output,
    materialize_tree,
    parse_junit_xml,
    run_pytest,
    suite_status,
)
```

Then append to the end of the file:

```python
_PASSING_TREE = {
    "calc.py": "def add(a, b):\n    return a + b\n",
    "test_calc.py": (
        "from calc import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
    ),
}

_FAILING_TREE = {
    "calc.py": "def add(a, b):\n    return a - b\n",
    "test_calc.py": (
        "from calc import add\n"
        "\n"
        "\n"
        "def test_add():\n"
        "    assert add(1, 2) == 3\n"
        "\n"
        "\n"
        "def test_zero():\n"
        "    assert add(0, 0) == 0\n"
    ),
}


def _sandbox_dirs() -> set:
    return set(Path(tempfile.gettempdir()).glob("agent-eval-sandbox-*"))


def test_run_pytest_passing_tree() -> None:
    result = run_pytest(_PASSING_TREE, timeout_s=30.0)
    assert result.status == "passed"
    assert result.exit_code == 0
    assert (result.passed, result.failed, result.errors, result.skipped) == (
        1,
        0,
        0,
        0,
    )
    assert result.tests == (
        TestCaseResult(test_id="test_calc::test_add", status="passed"),
    )
    assert "1 passed in <duration>" in result.stdout


def test_run_pytest_failing_tree_reports_per_test_statuses() -> None:
    result = run_pytest(_FAILING_TREE, timeout_s=30.0)
    assert result.status == "failed"
    assert result.exit_code == 1
    assert (result.passed, result.failed) == (1, 1)
    assert result.tests == (
        TestCaseResult(test_id="test_calc::test_add", status="failed"),
        TestCaseResult(test_id="test_calc::test_zero", status="passed"),
    )
    assert "1 failed, 1 passed in <duration>" in result.stdout
    assert "agent-eval-sandbox-" not in result.stdout


def test_run_pytest_cleans_up_its_sandbox() -> None:
    before = _sandbox_dirs()
    run_pytest(_PASSING_TREE, timeout_s=30.0)
    assert _sandbox_dirs() == before


def test_sandbox_env_hides_parent_secrets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EVAL_LAB_SENTINEL", "leak-me")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-fake-secret")
    tree = {
        "test_env.py": (
            "import os\n"
            "\n"
            "\n"
            "def test_clean_env():\n"
            "    assert 'EVAL_LAB_SENTINEL' not in os.environ\n"
            "    assert 'OPENROUTER_API_KEY' not in os.environ\n"
        )
    }
    result = run_pytest(tree, timeout_s=30.0)
    assert result.status == "passed"
```

- [ ] **Step 8.2: Run the tests to verify they fail**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: FAIL — collection error, `ImportError: cannot import name 'run_pytest'`.

- [ ] **Step 8.3: Implement `run_pytest` (no timeout handling yet — Task 10 adds it red-green)**

In `src/agent_eval_lab/runners/pytest_edge.py`, replace exactly this block:

```python
import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

from agent_eval_lab.records.execution import (
    SuiteStatus,
    TestCaseResult,
    TestStatus,
)

SANDBOX_PLACEHOLDER = "<sandbox>"
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")
```

with:

```python
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path

from agent_eval_lab.records.execution import (
    ExecutionResult,
    SuiteStatus,
    TestCaseResult,
    TestStatus,
    truncate_output,
)

SANDBOX_PLACEHOLDER = "<sandbox>"
DEFAULT_TIMEOUT_S = 10.0
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")
```

Then append to the end of the file:

```python
def _sandbox_env(root: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ, so secrets cannot leak."""
    return {
        "PYTHONHASHSEED": "0",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "TZ": "UTC",
        "HOME": root,
        "PYTHONPATH": root,
        "PATH": "/usr/bin:/bin",
    }


def _count(cases: tuple[TestCaseResult, ...], status: str) -> int:
    return sum(1 for case in cases if case.status == status)


def _build_result(
    *,
    exit_code: int,
    cases: tuple[TestCaseResult, ...],
    stdout: str,
    stderr: str,
) -> ExecutionResult:
    return ExecutionResult(
        status=suite_status(exit_code),
        exit_code=exit_code,
        passed=_count(cases, "passed"),
        failed=_count(cases, "failed"),
        errors=_count(cases, "error"),
        skipped=_count(cases, "skipped"),
        tests=cases,
        stdout=stdout,
        stderr=stderr,
    )


def _read_cases(xml_path: Path) -> tuple[TestCaseResult, ...]:
    if not xml_path.exists():
        return ()
    return parse_junit_xml(xml_path.read_text(encoding="utf-8"))


def _canonical(stream: bytes, root: Path) -> str:
    text = stream.decode("utf-8", errors="replace")
    return truncate_output(canonicalize_output(text, str(root)))


def _execute(root: Path, timeout_s: float) -> ExecutionResult:
    xml_path = root / ".junit.xml"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        f"--junitxml={xml_path}",
        "-p",
        "no:cacheprovider",
    ]
    process = subprocess.Popen(
        command,
        cwd=root,
        env=_sandbox_env(str(root)),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    stdout, stderr = process.communicate(timeout=timeout_s)
    return _build_result(
        exit_code=process.returncode,
        cases=_read_cases(xml_path),
        stdout=_canonical(stdout, root),
        stderr=_canonical(stderr, root),
    )


def run_pytest(
    files: Mapping[str, str], timeout_s: float = DEFAULT_TIMEOUT_S
) -> ExecutionResult:
    """Run pytest over a materialized file tree; deterministic record out.

    The root is resolved at creation so exactly one path spelling exists
    (macOS: /private/var/...), making canonicalization a single replacement.
    """
    root = Path(tempfile.mkdtemp(prefix="agent-eval-sandbox-")).resolve()
    try:
        materialize_tree(files, root)
        return _execute(root, timeout_s)
    finally:
        shutil.rmtree(root, ignore_errors=True)
```

- [ ] **Step 8.4: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `15 passed` (takes a few seconds — four real pytest subprocesses).

- [ ] **Step 8.5: Commit**

```bash
git add tests/runners/test_pytest_edge.py src/agent_eval_lab/runners/pytest_edge.py
git commit -m "feat(runners): run_pytest sandbox — hermetic scrubbed env, junit parse, cleanup"
```

---

### Task 9: Edge integration matrix — collection error, no tests, skips

**Files:**
- Modify: `tests/runners/test_pytest_edge.py` (append)

These three exercise composition of pieces already unit-tested (exit classification + XML parse + canonicalization), so they are expected GREEN on arrival (they accompany the same commit series — criterion 14). If any fails, STOP and fix the edge.

- [ ] **Step 9.1: Append the matrix tests**

Append to the end of `tests/runners/test_pytest_edge.py`:

```python
def test_run_pytest_collection_error_tree() -> None:
    result = run_pytest(
        {"test_broken.py": "import missing_module\n"}, timeout_s=30.0
    )
    assert result.status == "error"
    assert result.exit_code == 2
    assert result.errors == 1
    assert result.tests == (
        TestCaseResult(test_id="::test_broken", status="error"),
    )
    assert "<sandbox>" in result.stdout
    assert "agent-eval-sandbox-" not in result.stdout


def test_run_pytest_no_tests_tree() -> None:
    result = run_pytest({"calc.py": "x = 1\n"}, timeout_s=30.0)
    assert result.status == "no_tests"
    assert result.exit_code == 5
    assert result.tests == ()
    assert "no tests ran in <duration>" in result.stdout


def test_run_pytest_counts_skipped_tests() -> None:
    tree = {
        "test_skip.py": (
            "import pytest\n"
            "\n"
            "\n"
            "def test_ok():\n"
            "    assert True\n"
            "\n"
            "\n"
            "@pytest.mark.skip(reason='later')\n"
            "def test_later():\n"
            "    assert False\n"
        )
    }
    result = run_pytest(tree, timeout_s=30.0)
    assert result.status == "passed"
    assert result.exit_code == 0
    assert (result.passed, result.skipped) == (1, 1)
    assert result.tests == (
        TestCaseResult(test_id="test_skip::test_later", status="skipped"),
        TestCaseResult(test_id="test_skip::test_ok", status="passed"),
    )
```

- [ ] **Step 9.2: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `18 passed`. The collection-error test is the observable proof of `<sandbox>` canonicalization (the import-error message embeds the absolute temp root).

- [ ] **Step 9.3: Commit**

```bash
git add tests/runners/test_pytest_edge.py
git commit -m "test(runners): execution edge integration matrix — error/no_tests/skipped"
```

---

### Task 10: Structured timeout with process-group reaping

**Files:**
- Modify: `tests/runners/test_pytest_edge.py` (append)
- Modify: `src/agent_eval_lab/runners/pytest_edge.py`

- [ ] **Step 10.1: Append the failing test**

Append to the end of `tests/runners/test_pytest_edge.py`:

```python
def test_run_pytest_timeout_is_structured_and_reaped() -> None:
    tree = {
        "test_hang.py": (
            "import time\n"
            "\n"
            "\n"
            "def test_hang():\n"
            "    time.sleep(30)\n"
        )
    }
    before = _sandbox_dirs()
    result = run_pytest(tree, timeout_s=1.0)
    assert result.status == "timeout"
    assert result.exit_code == -9
    assert result.tests == ()
    assert (result.passed, result.failed, result.errors, result.skipped) == (
        0,
        0,
        0,
        0,
    )
    assert result.stdout == ""
    assert result.stderr == ""
    assert _sandbox_dirs() == before
```

- [ ] **Step 10.2: Run the test to verify it fails**

Run: `uv run pytest tests/runners/test_pytest_edge.py::test_run_pytest_timeout_is_structured_and_reaped`
Expected: FAIL — the test errors with `subprocess.TimeoutExpired` (the edge does not handle timeouts yet). A sleeping child may linger up to ~30 s after this red run; that is expected and disappears once green.

- [ ] **Step 10.3: Implement timeout handling**

In `src/agent_eval_lab/runners/pytest_edge.py`, replace exactly this block:

```python
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from pathlib import Path
```

with:

```python
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
```

Then replace exactly this block:

```python
SANDBOX_PLACEHOLDER = "<sandbox>"
DEFAULT_TIMEOUT_S = 10.0
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")
```

with:

```python
SANDBOX_PLACEHOLDER = "<sandbox>"
DEFAULT_TIMEOUT_S = 10.0
_TIMEOUT_EXIT_CODE = -9
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")
```

Then replace exactly this block:

```python
def _canonical(stream: bytes, root: Path) -> str:
    text = stream.decode("utf-8", errors="replace")
    return truncate_output(canonicalize_output(text, str(root)))
```

with:

```python
def _canonical(stream: bytes, root: Path) -> str:
    text = stream.decode("utf-8", errors="replace")
    return truncate_output(canonicalize_output(text, str(root)))


def _timeout_result() -> ExecutionResult:
    return ExecutionResult(
        status="timeout",
        exit_code=_TIMEOUT_EXIT_CODE,
        passed=0,
        failed=0,
        errors=0,
        skipped=0,
        tests=(),
        stdout="",
        stderr="",
    )


def _kill_process_group(process: subprocess.Popen) -> None:
    """SIGKILL the whole session (start_new_session=True), then reap."""
    with suppress(ProcessLookupError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    process.communicate()
```

Then replace exactly this block:

```python
    stdout, stderr = process.communicate(timeout=timeout_s)
    return _build_result(
```

with:

```python
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        return _timeout_result()
    return _build_result(
```

- [ ] **Step 10.4: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `19 passed` (the timeout test takes ~1-2 s, not 30 — proof the group was killed).

- [ ] **Step 10.5: Commit**

```bash
git add tests/runners/test_pytest_edge.py src/agent_eval_lab/runners/pytest_edge.py
git commit -m "feat(runners): structured timeout — process-group SIGKILL, deterministic record"
```

---

### Task 11: Reproducibility — byte-identical serialized record

**Files:**
- Modify: `tests/runners/test_pytest_edge.py`

Expected GREEN on arrival — this is the property the whole canonicalization design exists to satisfy (MASTER-SPEC hard constraint, ADR-0009). If it fails, the recorded output still contains a nondeterministic token: STOP and extend `canonicalize_output`, never the test.

- [ ] **Step 11.1: Update the test imports and append the test**

In `tests/runners/test_pytest_edge.py`, replace exactly this block:

```python
import tempfile
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import TestCaseResult
```

with:

```python
import json
import tempfile
from pathlib import Path

import pytest

from agent_eval_lab.records.execution import (
    TestCaseResult,
    execution_result_to_dict,
)
```

Then append to the end of the file:

```python
def test_run_pytest_is_byte_identical_across_runs() -> None:
    first = run_pytest(_FAILING_TREE, timeout_s=30.0)
    second = run_pytest(_FAILING_TREE, timeout_s=30.0)
    first_bytes = json.dumps(
        execution_result_to_dict(first), sort_keys=True
    ).encode("utf-8")
    second_bytes = json.dumps(
        execution_result_to_dict(second), sort_keys=True
    ).encode("utf-8")
    assert first_bytes == second_bytes
```

- [ ] **Step 11.2: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_pytest_edge.py`
Expected: `20 passed`.

- [ ] **Step 11.3: Commit**

```bash
git add tests/runners/test_pytest_edge.py
git commit -m "test(runners): byte-identical serialized ExecutionResult across runs (ADR-0009)"
```

---

### Task 12: Loop fulfills effect-requests via executor

**Files:**
- Create: `tests/runners/test_loop_effects.py`
- Modify: `src/agent_eval_lab/runners/loop.py` (full-file replacement below)
- Verify unchanged: `tests/runners/test_loop.py` (do NOT edit it)

- [ ] **Step 12.1: Write the failing tests**

Create `tests/runners/test_loop_effects.py` with exactly:

```python
"""Effect-request fulfillment through the runner loop (ADR-0008)."""

import json

import httpx
import pytest

from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
    TestCaseResult,
    execution_result_to_dict,
)
from agent_eval_lab.records.turns import ToolFailure, ToolResultTurn, ToolSuccess
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.tasks.parse import parse_task
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.code_world import CODE_WORLD_TOOLS
from agent_eval_lab.tools.code_world import apply as code_world_apply

CONFIG = ProviderConfig(
    id="local", base_url="http://localhost:11434/v1", api_key_env="", model_id="m"
)

FILES = {"test_demo.py": "def test_ok():\n    assert True\n"}


def _task(files: dict[str, str]) -> Task:
    return parse_task(
        {
            "id": "cw-loop-001",
            "capability": "code_repair",
            "input": {
                "messages": [
                    {
                        "type": "message",
                        "role": "user",
                        "content": "Run the tests.",
                    }
                ],
                "available_tools": [
                    "read_file",
                    "write_file",
                    "list_files",
                    "run_tests",
                ],
            },
            "verification": {
                "type": "output_match",
                "expected_output": "Done.",
            },
            "metadata": {
                "split": "dev",
                "version": "1",
                "provenance": "hand_written",
            },
            "initial_state": {"files": files},
        }
    )


TASK = _task(FILES)

STUB_RESULT = ExecutionResult(
    status="failed",
    exit_code=1,
    passed=0,
    failed=1,
    errors=0,
    skipped=0,
    tests=(TestCaseResult(test_id="test_demo::test_ok", status="failed"),),
    stdout="1 failed in <duration>",
    stderr="",
)


def _tool_call_response(name: str, arguments: dict, call_id: str) -> dict:
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": call_id,
                            "type": "function",
                            "function": {
                                "name": name,
                                "arguments": json.dumps(arguments),
                            },
                        }
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 20, "completion_tokens": 10},
    }


def _final_response(content: str) -> dict:
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 30, "completion_tokens": 5},
    }


def _scripted_client(responses: list[dict]) -> httpx.Client:
    remaining = list(responses)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=remaining.pop(0))

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_loop_fulfills_execution_request_as_tool_success() -> None:
    seen: list[ExecutionRequest] = []

    def executor(request: ExecutionRequest) -> ExecutionResult:
        seen.append(request)
        return STUB_RESULT

    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=executor,
    )

    assert trajectory.stop_reason == "completed"
    result_turn = trajectory.turns[2]
    assert isinstance(result_turn, ToolResultTurn)
    expected = ToolSuccess(result=execution_result_to_dict(STUB_RESULT))
    assert result_turn.outcome == expected
    assert seen == [ExecutionRequest(files=FILES)]
    assert trajectory.final_state == {"files": FILES}


def test_failing_suite_is_still_tool_success() -> None:
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"


def test_fulfillment_matches_request_type_not_tool_name() -> None:
    def request_for_any_tool(*, registry, name, arguments, state):
        return state, ExecutionRequest(files=dict(state.get("files", {})))

    client = _scripted_client(
        [
            _tool_call_response("read_file", {"path": "test_demo.py"}, "c1"),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=request_for_any_tool,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert outcome == ToolSuccess(result=execution_result_to_dict(STUB_RESULT))


def test_execution_request_without_executor_raises_runtime_error() -> None:
    client = _scripted_client([_tool_call_response("run_tests", {}, "c1")])

    with pytest.raises(RuntimeError, match="executor"):
        run_single(
            task=TASK,
            registry=CODE_WORLD_TOOLS,
            config=CONFIG,
            http_client=client,
            run_index=0,
            max_steps=4,
            temperature=0.0,
            apply_fn=code_world_apply,
        )


def test_pure_validation_still_fails_as_tool_failure() -> None:
    client = _scripted_client(
        [
            _tool_call_response("read_file", {"path": "../etc/passwd"}, "c1"),
            _final_response("Done."),
        ]
    )

    trajectory = run_single(
        task=TASK,
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: STUB_RESULT,
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolFailure)
```

- [ ] **Step 12.2: Run the tests to verify they fail**

Run: `uv run pytest tests/runners/test_loop_effects.py`
Expected: FAIL — `TypeError: run_single() got an unexpected keyword argument 'apply_fn'` (5 failures).

- [ ] **Step 12.3: Replace `src/agent_eval_lab/runners/loop.py`**

Replace the entire content of `src/agent_eval_lab/runners/loop.py` with exactly:

```python
"""EDGE: the model<->tool loop. Holds state, threads it through pure `apply`.

Effect-requests (ADR-0008): when a world's apply returns an ExecutionRequest
in the outcome position, the loop fulfills it through the executor callable —
matched on the request type, never the tool-name string — and records the
fulfilled ToolSuccess (serialized ExecutionResult) on the trajectory. A
fulfilled request is always ToolSuccess, whatever the suite status;
ToolFailure stays reserved for pure validation.
"""

import json
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from agent_eval_lab.records.execution import (
    ExecutionRequest,
    ExecutionResult,
    execution_result_to_dict,
)
from agent_eval_lab.records.trajectory import ParseFailure, Trajectory, Usage
from agent_eval_lab.records.turns import (
    MessageTurn,
    ToolOutcome,
    ToolResultTurn,
    ToolSuccess,
    Turn,
)
from agent_eval_lab.runners.client import chat_completion
from agent_eval_lab.runners.config import ProviderConfig
from agent_eval_lab.runners.parse import parse_assistant_payload
from agent_eval_lab.runners.wire import tooldef_to_openai, turn_to_message
from agent_eval_lab.tasks.schema import Task
from agent_eval_lab.tools.workspace import ToolDef, apply

ApplyFn = Callable[..., tuple[Mapping[str, Any], ToolOutcome | ExecutionRequest]]
Executor = Callable[[ExecutionRequest], ExecutionResult]


def _fulfill(request: ExecutionRequest, executor: Executor | None) -> ToolSuccess:
    """Fulfill an effect-request at the edge; always ToolSuccess (ADR-0008)."""
    if executor is None:
        raise RuntimeError(
            "harness misconfiguration: apply returned an ExecutionRequest but "
            "no executor is configured"
        )
    return ToolSuccess(result=execution_result_to_dict(executor(request)))


def run_single(
    *,
    task: Task,
    registry: Mapping[str, ToolDef],
    config: ProviderConfig,
    http_client: httpx.Client,
    run_index: int,
    max_steps: int,
    temperature: float,
    apply_fn: ApplyFn = apply,
    executor: Executor | None = None,
) -> Trajectory:
    state = dict(task.initial_state or {})
    turns: list[Turn] = list(task.input.messages)
    missing = tuple(n for n in task.input.available_tools if n not in registry)
    if missing:
        raise ValueError(f"tools not in registry: {missing}")
    tools = tuple(
        tooldef_to_openai(registry[name]) for name in task.input.available_tools
    )
    prompt_tokens = 0
    completion_tokens = 0
    latency_s = 0.0
    parse_failure: ParseFailure | None = None
    stop_reason = "max_steps"

    for _ in range(max_steps):
        response = chat_completion(
            config=config,
            messages=tuple(turn_to_message(turn) for turn in turns),
            tools=tools,
            temperature=temperature,
            http_client=http_client,
        )
        usage = response.payload.get("usage", {})
        prompt_tokens += usage.get("prompt_tokens", 0)
        completion_tokens += usage.get("completion_tokens", 0)
        latency_s += response.latency_s
        choices = response.payload.get("choices") or []
        if not choices:
            parse_failure = ParseFailure(
                raw=json.dumps(dict(response.payload)),
                error="no choices in provider response",
            )
            stop_reason = "parse_failure"
            break
        parsed = parse_assistant_payload(choices[0].get("message", {}))
        if isinstance(parsed, ParseFailure):
            parse_failure = parsed
            stop_reason = "parse_failure"
            break
        turns.append(parsed)
        if isinstance(parsed, MessageTurn):
            stop_reason = "completed"
            break
        for call in parsed.tool_calls:
            state, applied = apply_fn(
                registry=registry,
                name=call.name,
                arguments=call.arguments,
                state=state,
            )
            outcome = (
                _fulfill(applied, executor)
                if isinstance(applied, ExecutionRequest)
                else applied
            )
            turns.append(ToolResultTurn(call_id=call.call_id, outcome=outcome))

    return Trajectory(
        turns=tuple(turns),
        usage=Usage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_s=latency_s,
        ),
        run_index=run_index,
        stop_reason=stop_reason,
        parse_failure=parse_failure,
        final_state=state,
    )
```

- [ ] **Step 12.4: Run the new tests to verify they pass**

Run: `uv run pytest tests/runners/test_loop_effects.py`
Expected: `5 passed`.

- [ ] **Step 12.5: Verify existing loop behavior is unchanged (criterion 12)**

Run: `git diff --stat tests/runners/test_loop.py && uv run pytest tests/runners/test_loop.py tests/runners/test_multi_run.py tests/test_cli.py`
Expected: empty diff (no output before the pytest line) and all tests pass — the workspace-world tests run against the new loop with defaults only.

- [ ] **Step 12.6: Commit**

```bash
git add tests/runners/test_loop_effects.py src/agent_eval_lab/runners/loop.py
git commit -m "feat(runners): loop fulfills effect-requests via executor, typed on request (ADR-0008)"
```

---

### Task 13: End-to-end — code-world loop through the real edge

**Files:**
- Modify: `tests/runners/test_loop_effects.py`

- [ ] **Step 13.1: Add the import and append the test**

In `tests/runners/test_loop_effects.py`, replace exactly this block:

```python
from agent_eval_lab.runners.loop import run_single
```

with:

```python
from agent_eval_lab.runners.loop import run_single
from agent_eval_lab.runners.pytest_edge import run_pytest
```

Then append to the end of the file:

```python
def test_loop_with_real_edge_records_failed_suite() -> None:
    failing = {"test_bug.py": "def test_bug():\n    assert 1 == 2\n"}
    client = _scripted_client(
        [_tool_call_response("run_tests", {}, "c1"), _final_response("Done.")]
    )

    trajectory = run_single(
        task=_task(failing),
        registry=CODE_WORLD_TOOLS,
        config=CONFIG,
        http_client=client,
        run_index=0,
        max_steps=4,
        temperature=0.0,
        apply_fn=code_world_apply,
        executor=lambda request: run_pytest(request.files, timeout_s=30.0),
    )

    outcome = trajectory.turns[2].outcome
    assert isinstance(outcome, ToolSuccess)
    assert outcome.result["status"] == "failed"
    assert outcome.result["failed"] == 1
    assert outcome.result["tests"] == [
        {"test_id": "test_bug::test_bug", "status": "failed"}
    ]
    assert "<duration>" in outcome.result["stdout"]
```

- [ ] **Step 13.2: Run the tests to verify they pass**

Run: `uv run pytest tests/runners/test_loop_effects.py`
Expected: `6 passed` (the new test spawns one real pytest subprocess).

- [ ] **Step 13.3: Commit**

```bash
git add tests/runners/test_loop_effects.py
git commit -m "test(runners): end-to-end code-world loop through the real pytest edge"
```

---

### Task 14: Final gates — format, lint, size budgets, full suite

- [ ] **Step 14.1: Format**

Run: `uv run ruff format .`
Expected: `N files reformatted` or `... files left unchanged`. If anything was reformatted, re-run the full suite afterwards (Step 14.3) before committing.

- [ ] **Step 14.2: Lint**

Run: `uv run ruff check .`
Expected: `All checks passed!` Fix any finding (likely import-sorting) and re-run until clean. Do not suppress with `noqa`.

- [ ] **Step 14.3: Full suite**

Run: `uv run pytest`
Expected: `435 passed` (363 baseline + 72 new: 8 records + 36 code_world + 2 properties + 20 pytest_edge + 6 loop_effects), with **no warnings** (`TestCaseResult.__test__ = False` prevents pytest collection warnings). REQUIRED: zero failures, zero errors, zero warnings, and `tests/runners/test_loop.py` untouched (`git diff --stat tests/runners/test_loop.py` prints nothing).

- [ ] **Step 14.4: Size budgets (constraint: each new module under ~200 lines)**

Run:

```bash
wc -l src/agent_eval_lab/records/execution.py \
      src/agent_eval_lab/tools/code_world.py \
      src/agent_eval_lab/runners/pytest_edge.py \
      src/agent_eval_lab/runners/loop.py
```

Expected (measured on the validated reference assembly, post-`ruff format`): execution ≈ 106, code_world ≈ 162, pytest_edge ≈ 213, loop ≈ 131. `pytest_edge` runs a few lines over the ~200 guideline because its docstring documents the security/limitation contract — keep the docstring; do not delete documentation to fit. Anything materially above these numbers means duplicated code: stop and deduplicate.

- [ ] **Step 14.5: Commit anything ruff touched**

```bash
git status --short
# only if files are listed:
git add -A && git commit -m "chore: ruff format/lint pass for item 001"
```

Do NOT push.

---

## Acceptance-criteria coverage map (self-review)

| Spec criterion | Where proven |
|---|---|
| 1. World module, 4 ToolDefs, closed schemas, widened return union | Task 2 (`test_registry_is_exactly_the_four_tools_with_closed_schemas`; `apply` signature in `code_world.py`) |
| 2. State shape, no-mutation + determinism properties | Task 5 (Hypothesis) |
| 3. Editing tools + mapping result shapes | Tasks 2-3 (read/write/list result dicts), Task 12 (`run_tests` → serialized `ExecutionResult` dict) |
| 4. Canonical path rule + collision rules | Task 2 (`BAD_PATHS` × read), Task 3 (`BAD_PATHS` × write, both collision directions) |
| 5. `run_tests` pure, state unchanged, no I/O | Task 4 (no filesystem/subprocess in `tools/code_world.py`; snapshot tests) |
| 6. Frozen serializable records, `status` literals, `skipped`, `classname::name`, 8 KiB cap, no duration | Task 1 (round-trips, exact-keys test, truncation tests) |
| 7. Edge: materialize/invoke/parse/canonicalize/cleanup | Tasks 6-8 (pure helpers unit-tested on captured XML; `finally` cleanup test) |
| 8. Hermetic from-scratch env | Task 8 (`test_sandbox_env_hides_parent_secrets` with sentinel + fake API key) |
| 9. Structured timeout, process-group kill, exit-code classification | Task 10 + Task 6 (`suite_status` table) |
| 10. Integration matrix (pass/fail/error/timeout/no_tests) | Tasks 8, 9, 10 |
| 11. Byte-identical reproducibility | Task 11 |
| 12. Loop fulfills generically, type-matched, always ToolSuccess, RuntimeError without executor, existing tests unchanged | Task 12 (5 tests + untouched `test_loop.py` gate) |
| 13. ADRs | Pre-existing (ADR-0008/0009, commit `bcaa522`) — no task |
| 14. TDD evidence | Every task: red step → green step → commit; green-on-arrival steps are labeled and justified (Tasks 5, 9, 11) |

## Judgment calls (spec gaps resolved by this plan)

1. **Timeout record contents** (criterion 9 is silent): empty `stdout`/`stderr`, `exit_code=-9`, zero counts — partial output after SIGKILL is timing-dependent and would break determinism; documented in the edge docstring.
2. **JUnit XML location**: `<root>/.junit.xml` inside the sandbox (spec says `--junitxml=<tmp>`), so one `rmtree` cleans everything; pytest overwrites any agent-planted file of that name before we read it.
3. **Serialization helpers** live in `records/execution.py`, not `serialize.py` — module-size budget and no edits to a stable file; trajectories carry the serialized dict as plain data so existing round-trips hold.
4. **Loop tests** go in a new `tests/runners/test_loop_effects.py` so `tests/runners/test_loop.py` stays byte-identical — that unchanged file *is* the proof of criterion 12's compatibility clause.
5. **Timing token replacement** pinned to `in <duration>` (ADR-0009 names the `<sandbox>` placeholder but not the timing spelling).
6. **Loop parameter names** pinned to `apply_fn` / `executor` (spec criterion 12 names the concepts, not the identifiers).
