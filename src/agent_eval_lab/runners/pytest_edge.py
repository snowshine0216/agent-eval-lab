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

from agent_eval_lab.records.execution import (
    ExecutionResult,
    SuiteStatus,
    TestCaseResult,
    TestStatus,
    truncate_output,
)

SANDBOX_PLACEHOLDER = "<sandbox>"
DEFAULT_TIMEOUT_S = 10.0
_TIMEOUT_EXIT_CODE = -9
_TIMING_TOKEN = re.compile(r"in \d+(?:\.\d+)?s\b")


def canonicalize_output(text: str, root: str) -> str:
    """Replace the sandbox root and pytest timing token (ADR-0009). Pure."""
    return _TIMING_TOKEN.sub("in <duration>", text.replace(root, SANDBOX_PLACEHOLDER))


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


def materialize_tree(files: Mapping[str, str], root: Path) -> None:
    """Write the tree under root: sorted order, parents created, UTF-8.

    Defense in depth: refuses any resolved target outside root, even though
    the pure tools already reject non-canonical paths.
    """
    resolved_root = root.resolve()
    for path in sorted(files):
        target = (resolved_root / path).resolve()
        if not target.is_relative_to(resolved_root):
            raise RuntimeError(f"refusing to materialize outside sandbox: {path!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(files[path], encoding="utf-8")


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


def _xml_parse_error_result(exit_code: int, exc: ET.ParseError) -> ExecutionResult:
    """Return a structured error record when the JUnit XML is unreadable."""
    message = truncate_output(f"junit-xml-parse-error: {exc}")
    return ExecutionResult(
        status="error",
        exit_code=exit_code,
        passed=0,
        failed=0,
        errors=0,
        skipped=0,
        tests=(),
        stdout="",
        stderr=message,
    )


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
    """SIGKILL the whole session (start_new_session=True), then reap.

    PermissionError: os.killpg/getpgid can raise EPERM on rare UID-transition.
    TimeoutExpired: a grandchild in its own session can inherit the pipes and
    survive the group SIGKILL, making communicate() block; cap the wait at 2s.
    """
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


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
    try:
        stdout, stderr = process.communicate(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        _kill_process_group(process)
        return _timeout_result()
    try:
        cases = _read_cases(xml_path)
    except ET.ParseError as exc:
        return _xml_parse_error_result(process.returncode, exc)
    return _build_result(
        exit_code=process.returncode,
        cases=cases,
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
