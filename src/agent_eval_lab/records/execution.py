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
            {"test_id": case.test_id, "status": case.status} for case in result.tests
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
