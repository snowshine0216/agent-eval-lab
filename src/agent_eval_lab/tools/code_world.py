"""code-world: pure tools over an immutable file tree (ADR-0008).

State shape: {"files": {posix-relative-path: text-content}}. The editing
tools return a ToolOutcome; `run_tests` returns an ExecutionRequest in the
outcome position — the effect-request the runner loop fulfills at the
execution edge. This module performs no I/O. Path canonical-form and
collision rules make every reachable state materializable by construction.
"""

import unicodedata
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


_HARNESS_RESERVED = frozenset({".junit.xml"})


def path_error(path: str) -> str | None:
    """Reject any spelling that is not canonical POSIX-relative form."""
    if "\\" in path or "\x00" in path:
        return f"invalid path {path!r}: backslash and NUL are forbidden"
    if any(segment in ("", ".", "..") for segment in path.split("/")):
        return f"invalid path {path!r}: not canonical POSIX-relative form"
    if path in _HARNESS_RESERVED:
        return f"path {path!r} is reserved by the harness and may not be written"
    return None


def _files(state: State) -> Mapping[str, str]:
    return state.get("files", {})


def _ancestors(path: str) -> tuple[str, ...]:
    segments = path.split("/")
    return tuple("/".join(segments[:i]) for i in range(1, len(segments)))


def _canonical(path: str) -> str:
    """Canonical form: NFC-normalize then casefold. Pure."""
    return unicodedata.normalize("NFC", path).casefold()


def _prefix_collision(new_path: str, existing_path: str) -> bool:
    """True when new_path and existing_path share a canonically identical prefix
    at some depth but spell it differently — unsafe on normalization-insensitive
    (APFS) or case-insensitive filesystems.

    Two paths with the exact same spelling are not a collision (overwrite allowed).
    Same-spelled directory, different filenames: not a collision.
    """
    if new_path == existing_path:
        return False
    new_segs = new_path.split("/")
    exist_segs = existing_path.split("/")
    shared_depth = min(len(new_segs), len(exist_segs))
    for i in range(shared_depth):
        # Build raw prefix up to this segment
        new_prefix = "/".join(new_segs[: i + 1])
        exist_prefix = "/".join(exist_segs[: i + 1])
        if new_prefix == exist_prefix:
            # Identical prefix so far — no collision at this level
            continue
        if _canonical(new_prefix) == _canonical(exist_prefix):
            # Canonical prefixes match but raw spellings differ — collision
            return True
        # Canonical prefixes differ — these paths diverge safely
        break
    return False


def _prefix_collision_error(path: str, files: Mapping[str, str]) -> str | None:
    """Reject writes that introduce a canonical prefix collision with any existing path.

    Subsumes the old casefold-only check: catches NFC/NFD pairs and directory-
    segment case collisions in addition to full-path case differences.
    Same-spelling overwrites remain allowed.
    """
    clash = next(
        (existing for existing in files if _prefix_collision(path, existing)),
        None,
    )
    if clash is None:
        return None
    return (
        f"path collision: {path!r} and existing {clash!r} "
        "differ only by normalization or case"
    )


def _collision_error(path: str, files: Mapping[str, str]) -> str | None:
    """Reject file/directory prefix collisions and normalization collisions."""
    if any(existing.startswith(path + "/") for existing in files):
        return f"path collision: {path!r} is a directory in the tree"
    clash = next((p for p in _ancestors(path) if p in files), None)
    if clash is not None:
        return f"path collision: {clash!r} is a file in the tree"
    return _prefix_collision_error(path, files)


def _read_file(args: Mapping[str, Any], state: State) -> tuple[State, ToolOutcome]:
    path = args["path"]
    error = path_error(path)
    if error is not None:
        return state, ToolFailure(error=error)
    content = _files(state).get(path)
    if content is None:
        return state, ToolFailure(error=f"no such file: {path}")
    return state, ToolSuccess(result={"path": path, "content": content})


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


def _run_tests(args: Mapping[str, Any], state: State) -> tuple[State, ExecutionRequest]:
    """Read-only over the tree: identical state + a frozen snapshot request."""
    return state, ExecutionRequest(files={**_files(state)})


ToolImpl = Callable[
    [Mapping[str, Any], State], tuple[State, ToolOutcome | ExecutionRequest]
]

_IMPLS: Mapping[str, ToolImpl] = {
    "read_file": _read_file,
    "write_file": _write_file,
    "list_files": _list_files,
    "run_tests": _run_tests,
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
