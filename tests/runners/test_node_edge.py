import os
import shutil

import pytest

from agent_eval_lab.runners.node_edge import (
    canonicalize_node_output,
    node_suite_status,
    run_node_tests,
)

_NODE = shutil.which(os.environ.get("NODE_BIN", "node"))
from agent_eval_lab.runners.node_edge import node_supports_junit  # noqa: E402

requires_node = pytest.mark.skipif(
    not node_supports_junit(), reason="node >=20 (junit reporter) required"
)

# Tiny self-contained ESM fixture: one passing node:test, no external imports.
_PASS_TEST = (
    "import test from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "test('one plus one', () => { assert.equal(1 + 1, 2); });\n"
)
_FAIL_TEST = (
    "import test from 'node:test';\n"
    "import assert from 'node:assert/strict';\n"
    "test('always fails', () => { assert.equal(1, 2); });\n"
)


def test_canonicalize_replaces_root_and_duration() -> None:
    raw = (
        "ok 1 - emits\n  ---\n  duration_ms: 0.04175\n  ...\n"
        "# duration_ms 46.712583\n/private/var/folders/x/agent-eval-node-1/out\n"
    )
    out = canonicalize_node_output(raw, "/private/var/folders/x/agent-eval-node-1")
    assert "0.04175" not in out
    assert "46.712583" not in out
    assert "duration_ms: <duration>" in out
    assert out.endswith("<sandbox>/out\n")


def test_suite_status_passed_when_exit_zero() -> None:
    assert node_suite_status(exit_code=0, testcase_count=35) == "passed"


def test_suite_status_failed_when_exit_one_with_cases() -> None:
    assert node_suite_status(exit_code=1, testcase_count=35) == "failed"


def test_suite_status_error_when_exit_one_no_cases() -> None:
    # missing test file / import crash: exit 1 but zero <testcase> parsed
    assert node_suite_status(exit_code=1, testcase_count=0) == "error"


def test_suite_status_error_on_other_codes() -> None:
    assert node_suite_status(exit_code=2, testcase_count=0) == "error"


@requires_node
def test_run_node_tests_passes_on_green_suite() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}', "pkg/x.test.js": _PASS_TEST},
        test_paths=("pkg/x.test.js",),
    )
    assert res.status == "passed"
    assert res.exit_code == 0
    assert res.passed == 1 and res.failed == 0


@requires_node
def test_run_node_tests_fails_on_red_suite() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}', "pkg/x.test.js": _FAIL_TEST},
        test_paths=("pkg/x.test.js",),
    )
    assert res.status == "failed"
    assert res.exit_code == 1
    assert res.failed == 1


@requires_node
def test_run_node_tests_errors_on_missing_file() -> None:
    res = run_node_tests(
        files={"pkg/package.json": '{"type":"module"}'},
        test_paths=("pkg/does-not-exist.test.js",),
    )
    assert res.status == "error"
