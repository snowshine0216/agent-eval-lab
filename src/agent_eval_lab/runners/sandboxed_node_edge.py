"""EDGE: confined `node --test tests/authored/` execution (ADR-0016, §B.4).

The UNTRUSTED sibling of node_edge.py. Where node_edge runs TRUSTED oracle code
un-sandboxed, this module runs the model's own AUTHORED tests under a macOS
sandbox-exec seatbelt that is deny-read-by-default with an explicit
read-allowlist (the candidate tree + node install dir + enumerated system
paths) plus deny-network and write-only-in-tree. The allowlist (not a broad
read-allow) is the security boundary: a broad (allow file-read*) would let model
JS read evaluator-only/ and print the golden to stdout, which is returned to the
model in-trajectory (deny network* alone does NOT close that channel).

node_edge.py (the trusted oracle path) is deliberately NOT touched here so its
frozen ExecutionResult records stay byte-stable (§9.7).

ESCALATION (ADR-0016): if this seatbelt allowlist cannot both start node AND
block an evaluator-only/ read on a given host, escalate to Docker --network none
with only the temp tree mounted. As of 2026-06-15 the seatbelt path is verified
working on macOS 26.5.1 + node v16.20.2, so Docker is NOT built.
"""

import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from contextlib import suppress
from pathlib import Path

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.node_feedback import (
    NodeFeedbackResult,
    render_feedback_tail,
)
from agent_eval_lab.runners.node_edge import canonicalize_node_output
from agent_eval_lab.runners.pytest_edge import materialize_tree

SANDBOX_EXEC = "/usr/bin/sandbox-exec"
DEFAULT_SYSTEM_READ_SUBPATHS: tuple[str, ...] = (
    "/usr/lib",
    "/usr/bin",
    "/bin",
    "/System",
    "/private/var/db/dyld",
)

AUTHORED_TEST_DIR = "tests/authored/"
DEFAULT_TIMEOUT_S = 30.0
_TIMEOUT_EXIT_CODE = -9
# node v16 TAP summary lines, e.g. "# pass 3" / "# fail 1".
_TAP_PASS = re.compile(r"^# pass (\d+)$", re.MULTILINE)
_TAP_FAIL = re.compile(r"^# fail (\d+)$", re.MULTILINE)


def seatbelt_profile(
    temp_tree: str,
    node_dir: str,
    *,
    extra_read_subpaths: tuple[str, ...] = DEFAULT_SYSTEM_READ_SUBPATHS,
) -> str:
    """Build the deny-default seatbelt profile (SBPL). Pure.

    temp_tree and node_dir MUST be resolved absolute paths with no trailing
    slash. Reads are enumerated (deny-default everywhere else); there is NO broad
    (allow file-read*). Writes are scoped to temp_tree; network is denied.
    """
    read_subpaths = (temp_tree, node_dir, *extra_read_subpaths)
    read_lines = "\n".join(f'(allow file-read* (subpath "{p}"))' for p in read_subpaths)
    return (
        "(version 1)\n"
        "(deny default)\n"
        '(import "system.sb")\n'
        "(allow process-exec)\n"
        "(allow process-fork)\n"
        "(allow file-read-metadata)\n"
        f"{read_lines}\n"
        "(deny network*)\n"
        f'(allow file-write* (subpath "{temp_tree}"))\n'
    )


def darwin_sandbox_available() -> bool:
    """True iff this host is macOS with an executable sandbox-exec.

    Mirrors node_supports_junit's probe shape: a cheap, side-effect-free
    capability check used to gate real V execution (skips on Linux CI).
    """
    if sys.platform != "darwin":
        return False
    return os.access(SANDBOX_EXEC, os.X_OK)


def node_install_paths() -> tuple[str, str]:
    """Return (resolved node binary, resolved node install dir). Edge (resolves
    a real path). The install dir is the binary's parent's parent (nvm layout:
    <ver>/bin/node -> allow subpath <ver>); falls back to the bin dir if the
    layout is flat.
    """
    resolved = shutil.which(os.environ.get("NODE_BIN", "node"))
    if resolved is None:
        raise RuntimeError("node binary not found (set NODE_BIN or add node to PATH)")
    node_bin = str(Path(resolved).resolve())
    bin_dir = Path(node_bin).parent
    install_dir = bin_dir.parent if bin_dir.name == "bin" else bin_dir
    return node_bin, str(install_dir)


def _node_env(root: str, node_dir: str) -> dict[str, str]:
    """From-scratch env (mirrors node_edge._node_env): never inherits os.environ."""
    return {
        "TZ": "UTC",
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "HOME": root,
        "PATH": f"/usr/bin:/bin:{node_dir}/bin",
        "NODE_OPTIONS": "",
        "NO_COLOR": "1",
    }


def _tap_count(text: str, pattern: re.Pattern) -> int:
    m = pattern.search(text)
    return int(m.group(1)) if m else 0


def _classify(exit_code: int, passed: int, failed: int) -> str:
    if exit_code == 0:
        return "passed"
    if exit_code == 1 and (passed or failed):
        return "failed"
    return "error"


def _kill_process_group(process: subprocess.Popen) -> None:
    with suppress(ProcessLookupError, PermissionError):
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    with suppress(subprocess.TimeoutExpired):
        process.communicate(timeout=2.0)


def run_authored_tests_sandboxed(
    files: Mapping[str, str],
    *,
    node_bin: str,
    node_dir: str,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> NodeFeedbackResult:
    """Materialize the tree, run `node --test tests/authored/` UNDER the seatbelt
    profile, render tail-aware feedback. Edge (subprocess/FS). Deterministic out.
    """
    root = Path(tempfile.mkdtemp(prefix="agent-eval-vsbx-")).resolve()
    try:
        materialize_tree(files, root)
        profile_path = root / ".profile.sb"
        profile_path.write_text(seatbelt_profile(str(root), node_dir), encoding="utf-8")
        command = [
            SANDBOX_EXEC,
            "-f",
            str(profile_path),
            node_bin,
            "--test",
            AUTHORED_TEST_DIR,
        ]
        process = subprocess.Popen(
            command,
            cwd=root,
            env=_node_env(str(root), node_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=timeout_s)
        except subprocess.TimeoutExpired:
            _kill_process_group(process)
            return NodeFeedbackResult(
                status="timeout",
                exit_code=_TIMEOUT_EXIT_CODE,
                passed=0,
                failed=0,
                output="",
            )
        merged = canonicalize_node_output(
            stdout.decode("utf-8", "replace") + stderr.decode("utf-8", "replace"),
            str(root),
        )
        passed = _tap_count(merged, _TAP_PASS)
        failed = _tap_count(merged, _TAP_FAIL)
        return NodeFeedbackResult(
            status=_classify(process.returncode, passed, failed),
            exit_code=process.returncode,
            passed=passed,
            failed=failed,
            output=render_feedback_tail(merged),
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def make_authored_test_executor(
    *,
    node_bin: str,
    node_dir: str,
    run_fn: Callable[..., NodeFeedbackResult] = run_authored_tests_sandboxed,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Callable[[ExecutionRequest], NodeFeedbackResult]:
    """Build the V executor: an injected callable the loop fulfils run_tests with.

    It IGNORES model-supplied request contents beyond the snapshotted tree and
    ALWAYS runs the fixed `node --test tests/authored/` (model-supplied commands
    are rejected by construction — there is no path for them). tests/authored/ is
    a reserved writable dir no seeded tree populates, so F3's seeded causal tests
    are never run as feedback. Reserved-path scoping is provenance; the seatbelt
    sandbox is the security boundary (§B.4). run_fn injected for tests.
    """

    def executor(request: ExecutionRequest) -> NodeFeedbackResult:
        return run_fn(
            dict(request.files),
            node_bin=node_bin,
            node_dir=node_dir,
            timeout_s=timeout_s,
        )

    return executor
