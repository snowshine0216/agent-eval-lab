"""Effect-request bridge records for the D/B-set bash tool (ADR-0008).

BashRequest is what pure `apply` returns for the single `bash` tool: a command
string, nothing else (timeout, session, and env are edge policy). BashResult is
the deterministic record the bash edge produces; the loop records it as
ToolSuccess.result. Wall-clock duration is deliberately absent (the one
nondeterministic observable); stdout/stderr are truncated, never verbatim.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, kw_only=True)
class BashRequest:
    """Frozen snapshot of one shell command to run; nothing else."""

    command: str


@dataclass(frozen=True, kw_only=True)
class BashResult:
    """Deterministic record of one sandboxed bash command (no wall-clock)."""

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool


def bash_request_to_dict(request: BashRequest) -> dict[str, Any]:
    return {"command": request.command}


def bash_request_from_dict(data: Mapping[str, Any]) -> BashRequest:
    return BashRequest(command=data["command"])


def bash_result_to_dict(result: BashResult) -> dict[str, Any]:
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "exit_code": result.exit_code,
        "timed_out": result.timed_out,
    }


def bash_result_from_dict(data: Mapping[str, Any]) -> BashResult:
    return BashResult(
        stdout=data["stdout"],
        stderr=data["stderr"],
        exit_code=data["exit_code"],
        timed_out=data["timed_out"],
    )
