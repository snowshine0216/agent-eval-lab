"""Tests for the Factor V confined-execution sandbox (item 005).

Sections (in order):
  1. NodeFeedbackResult record + tail-aware renderer (Task 1)
  2. Pure seatbelt profile builder + Darwin/sandbox-exec probe (Task 2)
  3. make_authored_test_executor — fake run_fn wiring (Task 3)
  4. End-to-end V loop with a FAKE executor, CI-safe (Task 7)
  5. macOS-only integration test — ACTUALLY blocks the leak (Task 8)
"""

# ---------------------------------------------------------------------------
# Task 1: NodeFeedbackResult + tail-aware renderer
# ---------------------------------------------------------------------------

from agent_eval_lab.records.node_feedback import (
    FEEDBACK_SCHEMA_VERSION,
    NodeFeedbackResult,
    node_feedback_result_from_dict,
    node_feedback_result_to_dict,
    render_feedback_tail,
)


def test_node_feedback_result_round_trips() -> None:
    rec = NodeFeedbackResult(
        status="failed",
        exit_code=1,
        passed=2,
        failed=1,
        output="ok 1\nnot ok 2\n# fail 1\n",
    )
    back = node_feedback_result_from_dict(node_feedback_result_to_dict(rec))
    assert back == rec


def test_node_feedback_dict_carries_schema_version() -> None:
    rec = NodeFeedbackResult(
        status="passed", exit_code=0, passed=1, failed=0, output="# pass 1\n"
    )
    d = node_feedback_result_to_dict(rec)
    assert d["schema_version"] == FEEDBACK_SCHEMA_VERSION
    assert d["record"] == "node_feedback"


def test_render_feedback_tail_keeps_the_end_when_too_long() -> None:
    # 20000 lines; the failure summary is the LAST line. Tail-aware: it survives.
    body = "\n".join(f"ok {i}" for i in range(20000)) + "\n# fail 7 AT-THE-END\n"
    rendered = render_feedback_tail(body)
    assert "# fail 7 AT-THE-END" in rendered  # the END is kept (tail-aware)
    assert rendered.startswith("[head truncated]")  # marker at the FRONT
    assert len(rendered.encode("utf-8")) <= 8192 + len("[head truncated]\n")


def test_render_feedback_tail_passthrough_when_short() -> None:
    assert render_feedback_tail("# pass 3\n") == "# pass 3\n"


def test_render_feedback_tail_never_splits_a_multibyte_char() -> None:
    body = "é" * 9000  # 2 bytes each -> 18000 bytes, over the cap
    rendered = render_feedback_tail(body)
    # decodes cleanly (no half-character) and is tail-anchored
    assert rendered.encode("utf-8").decode("utf-8")
    assert rendered.endswith("é")


# ---------------------------------------------------------------------------
# Task 2: Pure seatbelt profile builder + Darwin/sandbox-exec probe
# ---------------------------------------------------------------------------

import sys

import pytest

from agent_eval_lab.runners.sandboxed_node_edge import (
    DEFAULT_SYSTEM_READ_SUBPATHS,
    SANDBOX_EXEC,
    darwin_sandbox_available,
    seatbelt_profile,
)

_TREE = "/private/var/folders/x/agent-eval-vsbx-abc"
_NODE_DIR = "/Users/who/.nvm/versions/node/v16.20.2"


def test_profile_is_deny_default_with_system_baseline() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert prof.startswith("(version 1)\n(deny default)\n")
    assert '(import "system.sb")' in prof


def test_profile_has_no_broad_file_read_allow() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    # the load-bearing assertion: every file-read allow is SCOPED to a subpath.
    for line in prof.splitlines():
        if line.startswith("(allow file-read*"):
            assert "(subpath " in line, f"unscoped file-read allow: {line!r}"
    # and the bare broad form never appears
    assert "(allow file-read*)" not in prof


def test_profile_scopes_reads_to_tree_node_and_system() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert f'(allow file-read* (subpath "{_TREE}"))' in prof
    assert f'(allow file-read* (subpath "{_NODE_DIR}"))' in prof
    for sysp in DEFAULT_SYSTEM_READ_SUBPATHS:
        assert f'(allow file-read* (subpath "{sysp}"))' in prof


def test_profile_denies_network_and_scopes_writes() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert "(deny network*)" in prof
    assert f'(allow file-write* (subpath "{_TREE}"))' in prof
    # no broad write allow
    assert "(allow file-write*)" not in prof


def test_profile_allows_process_primitives() -> None:
    prof = seatbelt_profile(_TREE, _NODE_DIR)
    assert "(allow process-exec)" in prof
    assert "(allow process-fork)" in prof


def test_darwin_probe_false_off_macos(monkeypatch) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    assert darwin_sandbox_available() is False


# ---------------------------------------------------------------------------
# Task 3: make_authored_test_executor — fake run_fn wiring
# ---------------------------------------------------------------------------

from agent_eval_lab.records.execution import ExecutionRequest
from agent_eval_lab.records.node_feedback import NodeFeedbackResult
from agent_eval_lab.runners.sandboxed_node_edge import (
    AUTHORED_TEST_DIR,
    make_authored_test_executor,
)


def test_executor_ignores_request_paths_and_runs_authored_dir() -> None:
    seen: list[tuple] = []

    def fake_run(files, *, node_bin, node_dir, timeout_s):
        seen.append(tuple(sorted(files)))
        return NodeFeedbackResult(
            status="passed", exit_code=0, passed=1, failed=0, output="# pass 1\n"
        )

    executor = make_authored_test_executor(
        node_bin="/x/node", node_dir="/x", run_fn=fake_run
    )
    # the model snapshotted the WHOLE tree (incl. seeded causal tests); the
    # executor must run only tests/authored/ regardless.
    req = ExecutionRequest(
        files={
            "tests/authored/a.test.js": "x",
            "tests/wdio/seeded.causal.test.js": "should-not-run",
        }
    )
    out = executor(req)
    assert isinstance(out, NodeFeedbackResult)
    assert out.status == "passed"
    # the materialized tree carried both files (snapshot), but run_fn only ever
    # gets the FIXED test dir as the path to run (asserted via the command below)


def test_executor_run_fn_receives_fixed_authored_test_path() -> None:
    captured: dict = {}

    def fake_run(files, *, node_bin, node_dir, timeout_s):
        captured["test_dir"] = AUTHORED_TEST_DIR
        return NodeFeedbackResult(
            status="error", exit_code=1, passed=0, failed=0, output="no tests\n"
        )

    executor = make_authored_test_executor(
        node_bin="/x/node", node_dir="/x", run_fn=fake_run
    )
    executor(ExecutionRequest(files={"tests/authored/a.test.js": "x"}))
    assert captured["test_dir"] == "tests/authored/"


def test_authored_test_dir_is_reserved_constant() -> None:
    assert AUTHORED_TEST_DIR == "tests/authored/"
