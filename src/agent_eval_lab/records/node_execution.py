"""Effect-request record for node --test execution (mirrors records/execution.py)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, kw_only=True)
class NodeExecutionRequest:
    """Frozen file-tree to run node --test over, plus the test paths to run."""

    files: Mapping[str, str]
    test_paths: tuple[str, ...]


def node_execution_request_to_dict(request: NodeExecutionRequest) -> dict[str, Any]:
    return {"files": dict(request.files), "test_paths": list(request.test_paths)}


def node_execution_request_from_dict(data: Mapping[str, Any]) -> NodeExecutionRequest:
    return NodeExecutionRequest(
        files=dict(data["files"]), test_paths=tuple(data["test_paths"])
    )
