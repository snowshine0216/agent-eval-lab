"""EDGE: sandboxed `node --test` execution boundary (F3 oracle, §18.6).

The node analogue of pytest_edge: materialize a file tree into a fresh temp
dir, run pinned-`node --test` with the JUnit reporter in a scrubbed
from-scratch environment under a hard timeout, parse the JUnit XML (shared
parser), canonicalize output, clean up in a finally. Deterministic, env-free.
"""

import os
import re
import shutil
import signal
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path

from agent_eval_lab.records.execution import (
    ExecutionResult,
    SuiteStatus,
    TestCaseResult,
    truncate_output,
)
from agent_eval_lab.runners.junit import parse_junit_xml
from agent_eval_lab.runners.pytest_edge import (
    SANDBOX_PLACEHOLDER,
    materialize_tree,
)

DEFAULT_TIMEOUT_S = 30.0
_TIMEOUT_EXIT_CODE = -9
# node emits `  duration_ms: 0.04175` (YAML) and `# duration_ms 46.7` (summary).
_NODE_DURATION = re.compile(r"duration_ms:?\s+\d+(?:\.\d+)?")


def canonicalize_node_output(text: str, root: str) -> str:
    """Replace the sandbox root and node duration tokens. Pure."""
    scrubbed = text.replace(root, SANDBOX_PLACEHOLDER)
    return _NODE_DURATION.sub("duration_ms: <duration>", scrubbed)


def node_suite_status(*, exit_code: int, testcase_count: int) -> SuiteStatus:
    """Classify a node --test run (probe-derived: no pytest-style code 5).

    0 -> passed; 1 with >=1 parsed testcase -> failed; 1 with zero testcases
    (missing file / import crash) -> error; anything else -> error.
    """
    if exit_code == 0:
        return "passed"
    if exit_code == 1 and testcase_count > 0:
        return "failed"
    return "error"


def _node_bin() -> str:
    resolved = shutil.which(os.environ.get("NODE_BIN", "node"))
    if resolved is None:
        raise RuntimeError("node binary not found (set NODE_BIN or add node to PATH)")
    return resolved


def node_supports_junit() -> bool:
    """True iff the resolvable node supports ``--test --test-reporter=junit``.

    The JUnit test reporter the F3 oracle depends on is stable from Node 20+;
    node 16/18 lack it. Used to gate node-based oracle runs (and the node-backed
    tests) so an incompatible/absent node SKIPS rather than fails. Pure-ish:
    one cheap ``node --version`` probe, no side effects beyond the subprocess.
    """
    resolved = shutil.which(os.environ.get("NODE_BIN", "node"))
    if resolved is None:
        return False
    try:
        out = subprocess.run(
            [resolved, "--version"], capture_output=True, text=True, timeout=10
        )
    except (OSError, subprocess.SubprocessError):
        return False
    major = out.stdout.strip().lstrip("v").split(".")[0]
    return major.isdigit() and int(major) >= 20


def _node_env(root: str) -> dict[str, str]:
    """From-scratch env: never inherits os.environ (no secrets, no proxies)."""
    return {
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": root,
        "PATH": "/usr/bin:/bin:" + str(Path(_node_bin()).parent),
        "NODE_OPTIONS": "",
        "NO_COLOR": "1",
    }


def _count(cases: tuple[TestCaseResult, ...], status: str) -> int:
    return sum(1 for case in cases if case.status == status)


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


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


def run_node_tests(
    files: Mapping[str, str],
    test_paths: tuple[str, ...],
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> ExecutionResult:
    """Run `node --test` over a materialized tree; deterministic record out."""
    root = Path(tempfile.mkdtemp(prefix="agent-eval-node-")).resolve()
    try:
        materialize_tree(files, root)
        xml_path = root / ".junit.xml"
        command = [
            _node_bin(),
            "--test",
            "--test-reporter=junit",
            f"--test-reporter-destination={xml_path}",
            *test_paths,
        ]
        process = subprocess.Popen(
            command,
            cwd=root,
            env=_node_env(str(root)),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return _timeout_result()
        # Mirror pytest_edge: a malformed/partial JUnit XML (disk-full, OS
        # interruption) must NOT crash grading. ET.ParseError inherits from
        # SyntaxError, so it would escape the (RuntimeError, OSError) catch in
        # node_oracle_edge — guard it here and classify the run as an error.
        try:
            cases = (
                parse_junit_xml(xml_path.read_text(encoding="utf-8"))
                if xml_path.exists()
                else ()
            )
        except ET.ParseError:
            return ExecutionResult(
                status="error",
                exit_code=process.returncode,
                passed=0,
                failed=0,
                errors=1,
                skipped=0,
                tests=(),
                stdout="",
                stderr="malformed JUnit XML from node --test (parse error)",
            )
        return ExecutionResult(
            status=node_suite_status(
                exit_code=process.returncode, testcase_count=len(cases)
            ),
            exit_code=process.returncode,
            passed=_count(cases, "passed"),
            failed=_count(cases, "failed"),
            errors=_count(cases, "error"),
            skipped=_count(cases, "skipped"),
            tests=cases,
            stdout=truncate_output(
                canonicalize_node_output(stdout.decode("utf-8", "replace"), str(root))
            ),
            stderr=truncate_output(
                canonicalize_node_output(stderr.decode("utf-8", "replace"), str(root))
            ),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)
